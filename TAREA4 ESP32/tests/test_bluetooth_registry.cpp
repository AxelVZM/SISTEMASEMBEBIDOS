#include "../DetectorTiempoReal/bluetooth_companies.h"
#include <cassert>
#include <fstream>
#include <string>
#include <iostream>
int main(int argc,char **argv){assert(argc==2);std::ifstream f(argv[1]);assert(f);std::string line;size_t count=0;while(std::getline(f,line)){auto split=line.find('\t');assert(split!=std::string::npos);auto id=std::stoi(line.substr(0,split));if(line.substr(split+1)!=detector::bluetoothCompany(id)){std::cerr<<id<<" expected "<<line.substr(split+1)<<" got "<<detector::bluetoothCompany(id)<<"\n";return 1;}count++;}assert(count==4049);std::cout<<"OK: 4049 official SIG names match lossless decoding\n";}
