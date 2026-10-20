#include "peripherals_stub.h"
#include <ctime>
#include <sys/time.h>
#include <cstdlib>
#include <iostream>
#include "../DetectorTiempoReal/count_core.h"
using namespace detector;
time_t fakeEpoch=0;time_t fakeTime(time_t *out){if(out)*out=fakeEpoch;return fakeEpoch;}int fakeSetTime(const timeval *value,const void*){fakeEpoch=value->tv_sec;return 0;}
struct FakeWire {std::map<uint8_t,std::vector<uint8_t>> registers;std::vector<uint8_t> tx,rx;uint8_t address=0,pointer=0;size_t at=0;bool fail=false;
 void begin(int,int,int){}void setTimeOut(int){}void beginTransmission(uint8_t a){address=a;tx.clear();}void write(uint8_t v){tx.push_back(v);}void write(const uint8_t *p,size_t n){tx.insert(tx.end(),p,p+n);}int endTransmission(bool=true){if(fail||!registers.count(address))return 1;if(!tx.empty()){pointer=tx[0];if(address==0x68)for(size_t i=1;i<tx.size();i++)registers[address][uint8_t(pointer+i-1)]=tx[i];}return 0;}size_t requestFrom(uint8_t a,uint8_t n){rx.clear();at=0;if(!fail&&registers.count(a))for(uint8_t i=0;i<n;i++)rx.push_back(registers[a][uint8_t(pointer+i)]);return rx.size();}size_t available(){return rx.size()-at;}uint8_t read(){return rx[at++];}
}Wire;
constexpr int OUTPUT=1;int ledValue=0;void pinMode(int,int){}void digitalWrite(int,bool value){ledValue=value;}
bool radioReady=true,bleFailed=false,fsReady=true,blePhase=false;uint8_t channel=6;CountSummary sample;CountSummary counts(uint32_t){return sample;}
#define time fakeTime
#define settimeofday fakeSetTime
bool networkBusy(){return false;}
#include "../DetectorTiempoReal/hardware.h"
#undef time
#undef settimeofday
int main(){
 Wire.registers[0x68]=std::vector<uint8_t>(256);Wire.registers[0x3c]=std::vector<uint8_t>(256);Wire.registers[0x68][0x0f]=0x80;
 initializeHardware();assert(rtcPresent&&oledReady&&!clockValid());assert(!rtcLoad());assert(!syncClock(1));assert(syncClock(1770000000));assert(clockValid());auto expected=fakeEpoch;fakeEpoch=0;assert(rtcLoad()&&fakeEpoch==expected);assert(Wire.registers[0x68][0x0f]==0);
 Wire.registers[0x68][5]=0x13;assert(!rtcLoad());syncClock(1770000000);Wire.registers[0x68][4]=0x31;Wire.registers[0x68][5]=0x02;assert(!rtcLoad());syncClock(1770000000);
 sample.wifi=96;sample.ble=32;sample.wifiCapacity=true;hardwareTick(1000);assert(oledReady);size_t nonzero=0;for(auto c:oledBuffer)nonzero+=c!=0;assert(nonzero);drawText(-10,-10,String(std::string(100,'A')),2);
 Wire.fail=true;hardwareTick(2000);assert(!oledReady);Wire.fail=false;hardwareTick(31000);assert(oledReady);Wire.registers.erase(0x68);probeHardware();assert(!rtcPresent);assert(syncClock(1770001000));assert(fakeEpoch==1770001000);
 std::cout<<"OK: optional I2C detection, RTC OSF/bounds/calendar/UTC sync, software clock, OLED pixel bounds/recovery, no required peripherals.\n";
}
