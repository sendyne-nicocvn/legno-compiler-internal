#include "AnalogLib.h"
#include <float.h>
#include "calib_util.h"
#include "fu.h"

float compute_init_cond(integ_code_t& m_codes){
  float sign = m_codes.inv[out0Id] ? -1.0 : 1.0;
  float rng = util::range_to_coeff(m_codes.range[out0Id]);
  float ic = m_codes.ic_val;
  return rng*sign*ic;
}

float compute_output(integ_code_t& m_codes,float val){
  float sign = m_codes.inv[out0Id] ? -1.0 : 1.0;
  float rng = util::range_to_coeff(m_codes.range[out0Id])
    /util::range_to_coeff(m_codes.range[in0Id]);
  return rng*sign*val;
}

float compute_steady_state_output(integ_code_t& m_codes, float in_val){
  float integ_scale = util::range_to_coeff(m_codes.range[out0Id]);
  integ_scale /= util::range_to_coeff(m_codes.range[in0Id]);
  float steady_state_scale = 1.0/(integ_scale);
  return in_val*steady_state_scale;
}


float compute_steady_state_input(integ_code_t& m_codes, float in_val){
  float input_scale = util::range_to_coeff(m_codes.range[in0Id]);
  float output_scale = util::range_to_coeff(m_codes.range[out0Id]);
  float integ_scale = output_scale/input_scale;
  float steady_state_scale = 1.0/(integ_scale);
  // scale input to fill integrator
  float coeff = input_scale;
  // divide the input scale by the gain of the steady state
  // to ensure we don't saturate the steady state
  if(steady_state_scale > 1.0){
    coeff /= steady_state_scale;
  }
  return coeff*in_val;
}

void Fabric::Chip::Tile::Slice::Integrator::update(integ_code_t codes){
  m_codes = codes;
  updateFu();
}
void Fabric::Chip::Tile::Slice::Integrator::setEnable (
	bool enable
) {
	m_codes.enable = enable;
	setParam0 ();
	setParam1 ();
	setParam3 ();
	setParam4 ();
}

void Fabric::Chip::Tile::Slice::Integrator::setInv (
                                                    ifc port,
                                                    bool inverse // whether output is negated
                                                    )
{
  if(!(port == out0Id)){
      error("cannot set inverse. invalid port");
  }
	m_codes.inv[port] = inverse;
	setEnable (
		m_codes.enable
	);
}

void Fabric::Chip::Tile::Slice::Integrator::setRange (ifc port,
                                                      range_t range) {
	/*check*/
  if(!(port == out0Id || port == in0Id)){
    error("cannot set range. invalid port");
  }
  m_codes.range[port] = range;
	setEnable (m_codes.enable);
}


void Fabric::Chip::Tile::Slice::Integrator::setInitialCode (
	unsigned char initialCode // fixed point representation of initial condition
) {
  m_codes.ic_code = initialCode;
  m_codes.ic_val = (initialCode-128)/128.0;
	setParam2 ();
}

bool Fabric::Chip::Tile::Slice::Integrator::setInitial(float initial)
{
  if(-1.0000001 < initial && initial < 1.000001){
    setInitialCode(min(initial*128.0+128.0,255));
    m_codes.ic_val = initial;
    return true;
  }
  else{
    return false;
  }
}


void Fabric::Chip::Tile::Slice::Integrator::setException (
	bool exception // turn on overflow detection
	// turning false overflow detection saves power if it is known to be unnecessary
) {
	m_codes.exception = exception;
	setParam1 ();
}

bool Fabric::Chip::Tile::Slice::Integrator::getException () const {
	unsigned char exceptionVector;
	parentSlice->parentTile->readExp ( exceptionVector );
	// bits 0-3: Integrator overflow
	SerialUSB.print (exceptionVector);
	SerialUSB.print (" ");
	return bitRead (exceptionVector, parentSlice->sliceId);
}
void Fabric::Chip::Tile::Slice::Integrator::defaults (){
  m_codes.pmos = 5;
  m_codes.nmos = 0;
  m_codes.ic_code = 128;
  m_codes.ic_val = 0.0;
  m_codes.inv[in0Id] = false;
  m_codes.inv[in1Id] = false;
  m_codes.inv[out0Id] = false;
  m_codes.range[in0Id] = RANGE_MED;
  m_codes.range[in1Id] = RANGE_UNKNOWN;
  m_codes.range[out0Id] = RANGE_MED;
  m_codes.cal_enable[in0Id] = false;
  m_codes.cal_enable[in1Id] = false;
  m_codes.cal_enable[out0Id] = false;
  m_codes.port_cal[in0Id] = 31;
  m_codes.port_cal[in1Id] = 0;
  m_codes.port_cal[out0Id] = 31;
  m_codes.exception = false;
  m_codes.gain_cal = 32;
	setAnaIrefNmos();
	setAnaIrefPmos();
}

Fabric::Chip::Tile::Slice::Integrator::Integrator (
	Chip::Tile::Slice * parentSlice
) :
	FunctionUnit(parentSlice, unitInt)
{
	in0 = new Interface(this, in0Id);
	tally_dyn_mem <Interface> ("IntegratorIn");
	out0 = new Interface(this, out0Id);
	tally_dyn_mem <Interface> ("IntegratorOut");
  defaults();
}

/*Set enable, invert, range*/
void Fabric::Chip::Tile::Slice::Integrator::setParam0 () const {
	intRange intRange;
  bool out0_loRange = (m_codes.range[out0Id] == RANGE_LOW);
  bool out0_hiRange = (m_codes.range[out0Id] == RANGE_HIGH);
  bool in0_loRange = (m_codes.range[in0Id] == RANGE_LOW);
  bool in0_hiRange = (m_codes.range[in0Id] == RANGE_HIGH);

	if (out0_loRange) {
		if (in0_loRange) {
			intRange = mGainLRng;
		} else if (in0_hiRange) {
			error ("cannot set integrator output loRange when input hiRange");
		} else {
			intRange = lGainLRng;
		}
	} else if (out0_hiRange) {
		if (in0_loRange) {
			error ("cannot set integrator output hiRange when input loRange");
		} else if (in0_hiRange) {
			intRange = mGainHRng;
		} else {
			intRange = hGainHRng;
		}
	} else {
		if (in0_loRange) {
			intRange = hGainMRng;
		} else if (in0_hiRange) {
			intRange = lGainMRng;
		} else {
			intRange = mGainMRng;
		}
	}

	unsigned char cfgTile = 0;
	cfgTile += m_codes.enable ? 1<<7 : 0;
	cfgTile += (m_codes.inv[out0Id]) ? 1<<6 : 0;
	cfgTile += intRange<<3;
	setParamHelper (0, cfgTile);
}

/*Set calIc, overflow enable*/
void Fabric::Chip::Tile::Slice::Integrator::setParam1 () const {
	unsigned char cfgCalIc = m_codes.gain_cal;
	if (cfgCalIc<0||63<cfgCalIc) error ("cfgCalIc out of bounds");
	unsigned char cfgTile = 0;
	cfgTile += cfgCalIc<<2;
	cfgTile += (m_codes.exception) ? 1<<1 : 0;
	setParamHelper (1, cfgTile);
}

/*Set initial condition*/
void Fabric::Chip::Tile::Slice::Integrator::setParam2 () const {
	setParamHelper (2, m_codes.ic_code);
}

/*Set calOutOs, calOutEn*/
void Fabric::Chip::Tile::Slice::Integrator::setParam3 () const {
	unsigned char calOutOs = m_codes.port_cal[out0Id];
	if (calOutOs<0||63<calOutOs) error ("calOutOs out of bounds");
	unsigned char cfgTile = 0;
	cfgTile += calOutOs<<2;
	cfgTile += (m_codes.cal_enable[out0Id]) ? 1<<1 : 0;
	setParamHelper (3, cfgTile);
}

/*Set calInOs, calInEn*/
void Fabric::Chip::Tile::Slice::Integrator::setParam4 () const {
	unsigned char calInOs = m_codes.port_cal[in0Id];
	if (calInOs<0||63<calInOs) error ("calInOs out of bounds");
	unsigned char cfgTile = 0;
	cfgTile += calInOs<<2;
	cfgTile += (m_codes.cal_enable[in0Id]) ? 1<<1 : 0;
	setParamHelper (4, cfgTile);
}

/*Helper function*/
void Fabric::Chip::Tile::Slice::Integrator::setParamHelper (
	unsigned char selLine,
	unsigned char cfgTile
) const {
	if (selLine<0||4<selLine) error ("selLine out of bounds");

	/*DETERMINE SEL_ROW*/
	unsigned char selRow;
	switch (parentSlice->sliceId) {
		case slice0: selRow = 2; break;
		case slice1: selRow = 3; break;
		case slice2: selRow = 4; break;
		case slice3: selRow = 5; break;
		default: error ("invalid slice. Only slices 0 through 3 have INTs"); break;
	}

	Vector vec = Vector (
		*this,
		selRow,
		2,
		selLine,
		endian (cfgTile)
	);

	parentSlice->parentTile->parentChip->cacheVec (
		vec
	);
}


void Fabric::Chip::Tile::Slice::Integrator::setAnaIrefNmos () const {
	unsigned char selRow=0;
	unsigned char selCol=2;
	unsigned char selLine;
  util::test_iref(m_codes.nmos);
	switch (parentSlice->sliceId) {
		case slice0: selLine=1; break;
		case slice1: selLine=2; break;
		case slice2: selLine=0; break;
		case slice3: selLine=3; break;
		default: error ("INT invalid slice"); break;
	}
	unsigned char cfgTile = endian(parentSlice->parentTile->parentChip->cfgBuf[parentSlice->parentTile->tileRowId][parentSlice->parentTile->tileColId][selRow][selCol][selLine]);
	cfgTile = (cfgTile & 0b00000111) + ((m_codes.nmos<<3) & 0b00111000);

	Vector vec = Vector (
		*this,
		selRow,
		selCol,
		selLine,
		endian (cfgTile)
	);

	parentSlice->parentTile->parentChip->cacheVec (
		vec
	);

}

void Fabric::Chip::Tile::Slice::Integrator::setAnaIrefPmos () const {

	unsigned char selRow=0;
	unsigned char selCol;
	unsigned char selLine;
  util::test_iref(m_codes.pmos);
	switch (parentSlice->sliceId) {
		case slice0: selCol=3; selLine=4; break;
		case slice1: selCol=3; selLine=5; break;
		case slice2: selCol=4; selLine=3; break;
		case slice3: selCol=4; selLine=4; break;
		default: error ("INT invalid slice"); break;
	}
	unsigned char cfgTile = endian(parentSlice->parentTile->parentChip->cfgBuf[parentSlice->parentTile->tileRowId][parentSlice->parentTile->tileColId][selRow][selCol][selLine]);
	switch (parentSlice->sliceId) {
		case slice0: cfgTile = (cfgTile & 0b00111000) + (m_codes.pmos & 0b00000111); break;
		case slice1: cfgTile = (cfgTile & 0b00000111) + ((m_codes.pmos<<3) & 0b00111000); break;
		case slice2: cfgTile = (cfgTile & 0b00111000) + (m_codes.pmos & 0b00000111); break;
		case slice3: cfgTile = (cfgTile & 0b00111000) + (m_codes.pmos & 0b00000111); break;
		default: error ("INT invalid slice"); break;
	}

	Vector vec = Vector (
		*this,
		selRow,
		selCol,
		selLine,
		endian (cfgTile)
	);

	parentSlice->parentTile->parentChip->cacheVec (
		vec
	);
}
