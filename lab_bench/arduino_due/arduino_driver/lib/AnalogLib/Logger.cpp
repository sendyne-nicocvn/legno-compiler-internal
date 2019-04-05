#include "include/Logger.h"
#include <Arduino.h>

namespace logger {

  void print(const char * msg){
    Serial.print(msg);
  }
  void print(int msg){
    Serial.print(msg);
  }
  void newline(){
    Serial.println("");
  }

  void header(){
    print("\nAC:>");
  }

  void tag(const char * msg){
    header();
    print("[");
    print(msg);
    print("]");
  }

  void log(const char * msg){
    tag("msg");
    print(msg);
  }
  void error(const char * msg){
    while(1){
      tag("error");
      print(msg);
      delay(100);
    }
  }

  void warn(const char * msg){
    tag("warn");
    print(msg);


  }
  void debug(const char * msg){
    tag("debug");
    print(msg);
  }

  void assert(bool assertion, const char * msg){
    if(assertion){
      return;
    }
    else{
      error(msg);
    }
  }

}
