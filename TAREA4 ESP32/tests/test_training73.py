import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('training',Path(__file__).resolve().parents[1]/'herramientas/entrenar_huellas.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(device,session,kind='phone',fp='01028284'):
    return dict(device_id=device,session_id=session,type=kind,brand='Synthetic test',model='Fixture only',source='Unit test, not measurements',fingerprint=fp,fingerprintVersion=1,fingerprintComplete=True)
class Tests(unittest.TestCase):
    def test_gate(self):
        train=[row('a','s1'),row('b','s2')];test=[row('c','s3'),row('d','s4','unknown','01029684')]
        c=m.train(train,test);self.assertEqual(len(c['entries']),1);self.assertEqual(c['validation']['coverage'],.5)
        self.assertEqual(m.train(train,[row('c','s3','unknown')])['entries'],[])
        self.assertEqual(m.train(train[:1],test)['entries'],[])
        self.assertEqual(m.train(train+[row('d','s4','laptop')],test[:1])['entries'],[])
    def test_leakage(self):
        with self.assertRaises(ValueError):m.train([row('a','s1')],[row('a','s2')])
        with self.assertRaises(ValueError):m.train([row('a','s1')],[row('b','s1')])
if __name__=='__main__':unittest.main()
