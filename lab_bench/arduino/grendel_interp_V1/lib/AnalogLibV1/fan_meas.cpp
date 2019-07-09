#include "AnalogLib.h"
#include "assert.h"
#include "calib_util.h"



profile_t Fabric::Chip::Tile::Slice::Fanout::measure(char mode, float input) {

  Fabric::Chip::Tile::Slice::Dac * val_dac = parentSlice->dac;
  int next_slice = (slice_to_int(parentSlice->sliceId) + 1) % 4;
  Dac * ref_dac = parentSlice->parentTile->slices[next_slice].dac;

  fanout_code_t codes_fan = m_codes;
  dac_code_t codes_dac = val_dac->m_codes;
  dac_code_t codes_ref_dac = ref_dac->m_codes;
  float in_target = input*util::range_to_coeff(m_codes.range[in0Id]);

  cutil::calibrate_t calib;
  cutil::initialize(calib);
  cutil::buffer_fanout_conns(calib,this);
  cutil::buffer_dac_conns(calib,ref_dac);
  cutil::buffer_dac_conns(calib,val_dac);
  cutil::buffer_tileout_conns(calib,&parentSlice->tileOuts[3]);
  cutil::buffer_chipout_conns(calib,
                              parentSlice->parentTile->parentChip
                              ->tiles[3].slices[2].chipOutput);
  cutil::break_conns(calib);

  dac_code_t dac_code_value;
  dac_code_t dac_code_ref;
  float ref;

  val_dac->setEnable(true);
  dac_code_value = cutil::make_val_dac(calib,val_dac,in_target);
  val_dac->update(dac_code_value);

  Connection dac_to_fan = Connection ( val_dac->out0, in0 );
  Connection tile_to_chip = Connection (parentSlice->tileOuts[3].out0,
                                parentSlice->parentTile->parentChip \
                                ->tiles[3].slices[2].chipOutput->in0);
  Connection ref_to_tile = Connection ( ref_dac->out0,
                                        parentSlice->tileOuts[3].in0 );

  dac_to_fan.setConn();
	tile_to_chip.setConn();
	ref_to_tile.setConn();
  unsigned char port = 0;
  float out_target;
  switch(mode){
  case 0:
    Connection (out0, this->parentSlice->tileOuts[3].in0).setConn();
    port = out0Id;
    out_target = in_target*util::sign_to_coeff(m_codes.inv[out0Id]);
    break;
  case 1:
    Connection(out1, this->parentSlice->tileOuts[3].in0).setConn();
    port = out1Id;
    out_target = in_target*util::sign_to_coeff(m_codes.inv[out1Id]);
    break;
  case 2:
    setThird(true);
    Connection(out2, this->parentSlice->tileOuts[3].in0).setConn();
    out_target = in_target*util::sign_to_coeff(m_codes.inv[out2Id]);
    port = out2Id;
    break;
  default:
    error("unknown mode");
  }
  ref_dac->setEnable(true);
  dac_code_ref = cutil::make_ref_dac(calib,
                                     ref_dac,
                                     -out_target,
                                     ref);
  ref_dac->update(dac_code_ref);

  float mean,variance;
	// Serial.print("\nFanout interface calibration");
  util::meas_dist_chip_out(this,mean,variance);
  profile_t prof = prof::make_profile(port,
                                      calib.success ? mode : 255,
                                      out_target,
                                      input,
                                      0.0,
                                      mean-(out_target+ref),
                                      variance);
  if(!calib.success){
    prof.mode = 255;
  }
  dac_to_fan.brkConn();
  tile_to_chip.brkConn();
  ref_to_tile.brkConn();
  switch(mode){
  case 0:
    Connection (out0, this->parentSlice->tileOuts[3].in0).brkConn();
    break;
  case 1:
    Connection(out2, this->parentSlice->tileOuts[3].in0).brkConn();
    break;
  case 2:
    setThird(false);
    Connection(out2, this->parentSlice->tileOuts[3].in0).brkConn();
    break;
  }
	setEnable ( false );
  cutil::restore_conns(calib);
  this->update(codes_fan);
  return prof;
}
