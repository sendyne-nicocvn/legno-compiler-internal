#ifndef EXPERIMENT_H
#define EXPERIMENT_H
#include <DueTimer.h>
#include "Circuit.h"
#include "math.h"

# define MAX_ADCS 4
# define MAX_DACS 2
// max value is 32000
# define MAX_SIZE 2000

namespace experiment {
  
typedef struct experiment_data {
  int n_samples;
  int max_samples;
  int osc_samples;
  int adc_offsets[MAX_ADCS];
  int dac_offsets[MAX_DACS];
  bool use_osc;
  bool compute_offsets;
  bool use_adc[MAX_ADCS];
  bool use_dac[MAX_DACS];
  bool use_analog_chip;
  // input data
  short databuf[MAX_SIZE];

} experiment_t;

typedef enum cmd_type {
  RESET,
  SET_DAC_VALUES,
  GET_ADC_VALUES,
  USE_ANALOG_CHIP,
  SET_SIM_TIME,
  USE_DAC,
  USE_ADC,
  USE_OSC,
  RUN,
  COMPUTE_OFFSETS,
  GET_NUM_SAMPLES,
  GET_TIME_BETWEEN_SAMPLES
} cmd_type_t;

typedef union args {
  float floats[3];
  uint32_t ints[3];
} args_t;
typedef struct cmd {
  uint16_t type;
  args_t args;
} cmd_t;

void setup_experiment();
void set_dac_value(experiment_t * expr, byte dac_id,int sample,float data);
void enable_adc(experiment_t * expr, byte adc_id);
void enable_oscilloscope(experiment_t * expr);
void enable_analog_chip(experiment_t * expr);
void reset_experiment(experiment_t * expr);
void enable_dac(experiment_t * expr, byte dac_id);
short* get_adc_values(experiment_t * expr, byte adc_id, int& num_samples);
void exec_command(experiment_t * expr, Fabric * fab, cmd_t& cmd, float* inbuf);
void print_command(cmd_t& cmd, float* inbuf);
}
#endif
