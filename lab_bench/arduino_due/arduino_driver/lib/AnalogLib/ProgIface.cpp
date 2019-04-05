#include "include/ProgIface.h"
#include "include/Util.h"
#include "include/Pin.h"
#include "include/SPI.h"

const bool noOp[] = {
	false, true, false, true,
	true, false, false, false,
	false, false, false, false,
	false, false, false, false,
	false, false, false, false,
	false, false, false, false
};

void ProgIface::_spiDriveData(
                   unsigned char tileno,
                   unsigned char row,
                   unsigned char col,
                   unsigned char line,
                   unsigned char cfg
                   ) const {
	DigitalWriteP(PIN_spiSSPin[m_chip][tileno], LOW);
	spiDrive ( row, col, line, cfg);
	DigitalWriteP(PIN_spiSSPin[m_chip][tileno], HIGH);
}

int ProgIface::_spiDriveInstr (unsigned char tileno,const bool* vector) const {
 	DigitalWriteP(PIN_spiSSPin[m_chip][tileno], LOW);
	// Serial.print("spiMisoPin = "); Serial.println(spiMisoPin);
	int result = spiDrive ( vector, PIN_spiMiso[m_chip][tileno] );
	// Serial.print("result = "); Serial.println(result);
	DigitalWriteP(PIN_spiSSPin[m_chip][tileno], HIGH);
	return result;
}
ProgIface::ProgIface(unsigned char iface){
  m_chip = iface;
}

void ProgIface::reset(){
  for (unsigned char tile=0; tile<N_TILES; tile++){
      for (unsigned char selRow=0; selRow<N_ROWS; selRow++){
        for (unsigned char selCol=(selRow==8?1:0); selCol<N_COLS; selCol++){
          for (unsigned char selLine=0; selLine<N_LINES; selLine++) {
            m_cfgTag[tile][selRow][selCol][selLine>>3] = 255;
            m_cfgBuf[tile][selRow][selCol][selLine] = 0;
          }
        }
      }
  }
}

void ProgIface::enqueue(vector_t vec){
	if (vec.row<0||N_ROWS-1<vec.row) error ("vec.selRow out of bounds");
	if (vec.col<0||N_COLS-1<vec.col) error ("vec.selCol out of bounds");
	if (vec.line<0||N_LINES-1<vec.line) error ("vec.selLine out of bounds");
	if (vec.row==8&&vec.col==0) error ("vec cache cannot handle ctlr cmmds");
	if (vec.cfg<0||255<vec.cfg) error ("vec.cfgTile out of bounds");

  if (m_cfgBuf[vec.tile][vec.row][vec.col][vec.line] != vec.cfg) {
		if (vec.row==9) m_cfgLutTag[vec.tile][0]=true;
		if (vec.row==10) m_cfgLutTag[vec.tile][1]=true;
		// m_cfgTag [vec.tileRowId] [vec.tileColId] [vec.selRow] [vec.selCol] [vec.selLine>>3] |= (1<<(vec.selLine&7));
		bitSet(m_cfgTag[vec.tile][vec.row][vec.col][vec.line>>3], vec.line&7);
		m_cfgBuf[vec.tile][vec.row][vec.col][vec.line] = vec.cfg;
	}

}



/*Write out vectors according to format choice
  0,0 = 0
  0,1 = 1
  1,0 = 2
  1,1 = 3
 */

void ProgIface::_startLUT(unsigned char tileno, unsigned char slice){
  unsigned char cfgTile = 0;
	cfgTile += SEL_LUT::CTRL_LUT<<2;
	cfgTile += SEL_LUT::CTRL_LUT<<0;

	/*DETERMINE SEL_COL*/
  unsigned char selRow = 7;
	unsigned char selCol;
	switch (slice) {
  case 0: selCol = 1; break;
  case 2: selCol = 2; break;
  default: error ("invalid slice. Only even slices have LUTs"); break;
	}

	_spiDriveData( tileno, selRow, selCol, 0, endian(cfgTile) );
	_spiDriveInstr(tileno,noOp);

}

void ProgIface::write() {

	// first eight rows are more typical
	for (unsigned char tile=0; tile<N_TILES; tile++){
    for (unsigned char row=0; row<8; row++){
      for (unsigned char col=0; col<N_COLS; col++){
					for (unsigned char tag=0; tag<N_TAGS; tag++) {
						unsigned char tagval = m_cfgTag[tile][row][col][tag];
						for (unsigned char byte=0; byte<8; byte++) {
							if (bitRead(tagval,byte)) { // if there are changes to make
                unsigned int value = m_cfgBuf[tile][row][col][tagval*8+byte];
								_spiDriveData(tile,row, col, tagval*8+byte, value);
							}
						}
						m_cfgTag[tile][row][col][tag] = 0;
					}
      }
    }
  }

	// LUT clauses!
	// lut needs to be put in ctlr input mode with calls to lutParam0
	// (7,1) LUT configuration and crossbar messages (See LUT Bits [12:23])
	for (unsigned char tile=0; tile<N_TILES; tile++) {
    // program values to LUT0
    if (m_cfgLutTag[tile][0]) { // if there are changes to make
				unsigned char lutTempL = m_cfgBuf[tile][7][1][0];
        _startLUT(tile,0);
				for (unsigned char row= 0; row< N_LUT_ROWS; row++) {
					for(unsigned char col= 0; col< N_LUT_COLS; col++) {
						unsigned char addr = row+ col*N_LUT_ROWS;
						unsigned char endianAddr = endian (addr);
						unsigned char selRow = 0b1001;
						unsigned char selCol = (endianAddr&0xf0) >> 4;
						unsigned char selLine = (endianAddr&0x0f) >> 0;
						_spiDriveData(tile,
                         selRow,
                         selCol,              \
                         selLine,                                       \
                         m_cfgBuf[tile][selRow][selCol][selLine]);
					}
				}
				_spiDriveData (tile,7,1,0,lutTempL); // original setting
				m_cfgLutTag[tile][0]=false;
			}

			// program values to LUT1
			if (m_cfgLutTag[tile][1]) { // if there are changes to make
				unsigned char lutTempR = m_cfgBuf[tile][7][2][0];
        _startLUT(tile,2);
				for (unsigned char row= 0; row< N_LUT_ROWS; row++) {
					for (unsigned char col= 0; col< N_LUT_COLS; col++) {
						unsigned char addr = row+ col* N_LUT_ROWS;
						unsigned char endianAddr = endian (addr);
						unsigned char selRow = 0b1010;
						unsigned char selCol = (endianAddr&0xf0) >> 4;
						unsigned char selLine = (endianAddr&0x0f) >> 0;
						_spiDriveData(tile,
                         selRow,
                         selCol,
                         selLine,
                         m_cfgBuf[tile][selRow][selCol][selLine]);
					}
				}
        _spiDriveData(tile,7,2,0,lutTempR);
				m_cfgLutTag[tile][0]=false;
			}
		}

}


