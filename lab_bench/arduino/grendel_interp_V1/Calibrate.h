#include "AnalogLib.h"
#include "calib_util.h"
#include "profile.h"
#ifndef CALIBRATE_H
#define CALIBRATE_H

namespace calibrate {
  profile_t measure(Fabric * fab,
                         uint16_t blk,
                         circ::circ_loc_idx1_t loc,
                         uint8_t mode,
                         float in0,
                         float in1);


  bool calibrate(Fabric * fab,
                 profile_t& result,
                 uint16_t blk,
                 circ::circ_loc_idx1_t loc,
                 const float max_error,
                 bool targeted);


  void get_codes(Fabric * fab,
                 uint16_t blk,
                 circ::circ_loc_idx1_t loc,
                 block_code_t& buf);

  void set_codes(Fabric * fab,
                 uint16_t blk,
                 circ::circ_loc_idx1_t loc,
                 block_code_t& buf);

}

#endif