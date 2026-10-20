#!/usr/bin/env python3
"""Lossless front coding of the attached IEEE header. Input is an uncompressed V6 ieee_data.h."""
import argparse,ast,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.source.read_text()
body=s.split('inline constexpr char organizations[]=')[1].split('inline constexpr Entry24 entries24[]=')[0];raw=b''.join(ast.literal_eval('b'+x) for x in re.findall(r'"(?:[^"\\]|\\.)*"',body))
if not raw.endswith(b'\0'):raw+=b'\0'
items=[];at=0
while at<len(raw):
 end=raw.index(0,at);items.append((raw[at:end],at));at=end+1
assert len(items)<65536
items.sort();mapping={old:i for i,(_,old) in enumerate(items)};blob=bytearray();blocks=[];previous=b''
for i,(name,_) in enumerate(items):
 if i%16==0:blocks.append(len(blob));previous=b''
 prefix=0
 while prefix<min(len(name),len(previous),255) and name[prefix]==previous[prefix]:prefix+=1
 blob.append(prefix);blob.extend(name[prefix:]);blob.append(0);previous=name
# Prove lossless decoding before emitting the compact header.
for i,(name,_) in enumerate(items):
 at=blocks[i//16];value=b''
 for _ in range(i%16+1):
  prefix=blob[at];end=blob.index(0,at+1);value=value[:prefix]+blob[at+1:end];at=end+1
 assert bytes(value)==name
lines=['#pragma once','#include <cstdint>','#include <cstddef>','// Lossless front coding of IEEE organization names; source hashes in data/ieee_manifest.json.','namespace ieee_mac {','struct __attribute__((packed)) Entry24 {uint32_t prefix;uint16_t offset;};','struct __attribute__((packed)) Entry36 {uint64_t prefix;uint16_t offset;};','inline constexpr uint8_t organizationData[]={']
for i in range(0,len(blob),32):lines.append(','.join(map(str,blob[i:i+32]))+',')
lines+=['};','inline constexpr uint32_t organizationBlocks[]={'+','.join(map(str,blocks))+'};',f'inline constexpr size_t ORGANIZATION_COUNT={len(items)};',f'inline constexpr size_t ORGANIZATION_BYTES={max(len(n) for n,_ in items)+1};','''inline const char *organizationAt(uint16_t index){
 static char out[ORGANIZATION_BYTES];size_t at=organizationBlocks[index/16];
 for(size_t row=0;row<=index%16;row++){size_t n=organizationData[at++];while(organizationData[at])out[n++]=char(organizationData[at++]);at++;out[n]=0;}return out;
}''']
count=0
for kind,typ in [('24','Entry24'),('28','Entry24'),('36','Entry36')]:
 rows=re.search(r'entries'+kind+r'\[\]=\{(.*?)\};',s,re.S)[1];entries=re.findall(r'\{(0x[0-9A-Fa-f]+)(?:u|ULL),(\d+)u\}',rows);assert entries;lines.append(f'inline constexpr {typ} entries{kind}[]={{')
 for key,offset in entries:lines.append('{'+key+('ULL' if kind=='36' else 'u')+','+str(mapping[int(offset)])+'u},')
 lines.append('};');count+=len(entries)
lines+=['inline constexpr size_t assignmentCount=sizeof(entries24)/sizeof(*entries24)+sizeof(entries28)/sizeof(*entries28)+sizeof(entries36)/sizeof(*entries36);','inline constexpr char snapshotDate[]="2026-10-19";','}'];a.output.write_text('\n'.join(lines)+'\n');print(count,'prefixes;',len(items),'names;',len(raw),'->',len(blob),'name bytes; no data removed')
