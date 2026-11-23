import importlib.util, pathlib, sys, types
root=pathlib.Path(__file__).resolve().parents[1]
serial=types.ModuleType('serial')
serial.SerialException=type('SerialException',(Exception,),{})
tools=types.ModuleType('serial.tools');ports=types.ModuleType('serial.tools.list_ports');ports.comports=lambda:[]
serial.tools=tools;tools.list_ports=ports
sys.modules.update({'serial':serial,'serial.tools':tools,'serial.tools.list_ports':ports})
spec=importlib.util.spec_from_file_location('bridge',root/'06_PUENTE_WINDOWS/puente_usb_aws.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
samples=['DHT22,18.00,47.5','CAL,18.00,47.50,TEMPLADO,TEMPLADO,TEMPLADO,0.02,0.96,0.02,2500','TINYML,22.4,45.0,CALIENTE,0.01,0.05,0.94,2300']
for raw in samples:
    obj=bridge.parse_line(raw)
    assert obj is not None, raw
    assert 0 <= obj['humedad']<=100
    print(raw.split(',')[0], '->',obj['clase_red'])
assert bridge.parse_line('READY,DHT22,GPIO13') is None
assert bridge.parse_line('CAL,nan,20,FRIO,FRIO,FRIO,0,0,1,2') is None
print('Parseo verificado sin dispositivos fisicos')
