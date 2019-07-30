#ifndef PROG_IFACE
#define PROG_IFACE

#include "include/Globals.h"
#include "include/Vector.h"
#include "include/Layout.h"

#define N_ROWS 11
#define N_COLS  16
#define N_LINES  16
#define N_TAGS 2

#define N_LUT_ROWS 32
#define N_LUT_COLS 8


typedef enum STATE_ {
  CONFIGURE,
  EXECUTE,
  STANDBY
} STATE;

typedef enum {
 ADCL= 0,
 ADCR= 1,
 EXTLUT= 2,
 CTRL_LUT= 3,
} SEL_LUT;

class ProgIface{
 public:
  ProgIface(unsigned char iface);
  void reset();
  unsigned char get(const vector_t vec) const;
  void enqueue(const vector_t vec);
  void set(loc_t loc, const char data);
  void set_state(STATE state);
  void write();
 private:
  void _spiDriveData(unsigned char tileno, unsigned char row, unsigned char col,
                    unsigned char line, unsigned char cfg) const;
  int _spiDriveInstr(unsigned char tileno,const bool* vector) const;

  void _startLUT(unsigned char tileno, unsigned char slice);
  void _check(const vector_t vec) const;
  int m_chip;
  bool m_dryrun;
  unsigned char m_cfgTag [N_TILES][N_ROWS][N_COLS][N_TAGS]; // bit indicating configuration has changed
  bool m_cfgLutTag[2][N_TILES]; // bit indicating configuration has changed
  unsigned char m_cfgBuf[N_TILES][N_ROWS][N_COLS][N_LINES]; // buffer for all the configuration writes
};

#endif