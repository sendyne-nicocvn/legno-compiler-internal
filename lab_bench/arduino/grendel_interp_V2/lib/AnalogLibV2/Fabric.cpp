#include "include/Fabric.h"
#include "include/Pin.h"
#include "include/ProgIface.h"
#include "include/Block.h"
#include "include/Logger.h"

Fabric::Fabric () {
	/*SPI PINS*/
	m_ifaces = new ProgIface[2] {
		ProgIface(0),
		ProgIface(1)
	};
}

Fabric::~Fabric() {
  delete [] m_ifaces;
}
block_t Fabric::block(BLOCK_TYPE type,
                   unsigned char chip,
                   unsigned char tile,
                   unsigned char slice,
                   unsigned char index){
  block_t blk = block::mkblock(type,chip,tile,slice,index);
  blk.iface = &m_ifaces[chip];
  return blk;

}

void Fabric::initialize(){
  logger::debug("setting up..");
  pin::setup();
  /*scan chain disable*/
  logger::debug("reset config..");
  pin::reset();
	/*create chips*/ 
}
void Fabric::prog_commit(){
}

void Fabric::prog_start(){
}

void Fabric::prog_done(){
}

void Fabric::run_sim(){
}
void Fabric::stop_sim(){
}