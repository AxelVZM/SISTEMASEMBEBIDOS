"""POSIX pseudo-terminal integration: real pyserial, no physical radio simulated as real."""
import asyncio,contextlib,importlib,json,os,time
import pytest

@pytest.mark.skipif(os.name=='nt',reason='La prueba PTY requiere POSIX; ejecutar las demás pruebas en Windows.')
def test_serial_stream_ack_disconnect_reconnect(tmp_path,monkeypatch):
    import pty,tty
    monkeypatch.setenv('DETECTOR_DATA',str(tmp_path))
    import backend.main as module
    importlib.reload(module)
    async def run():
        master,slave=pty.openpty();tty.setraw(slave);path=os.ttyname(slave)
        rt=module.Runtime();rt.settings.port=path
        task=asyncio.create_task(module.serial_loop(rt))
        async def until(predicate,seconds=6):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if predicate():return
                await asyncio.sleep(.03)
            raise AssertionError('Tiempo de espera serial agotado')
        try:
            await until(lambda:rt.connected)
            status=dict(event='status',firmware='1.0.0',boot_id=123,phase='wifi',uptime_ms=1000,queue_dropped=0,free_heap=100000)
            os.write(master,(json.dumps(status)+'\n').encode())
            await until(lambda:rt.pending is not None)
            command=await asyncio.to_thread(os.read,master,2048)
            assert json.loads(command)['channels']==list(range(1,12))
            os.write(master,(json.dumps(dict(event='ack',id=rt.pending,state='applied'))+'\n').encode())
            await until(lambda:rt.applied is not None)
            observation=b'{"event":"observation","tech":"ble","mac":"AA:BB:CC:11:22:33","rssi":-65,"address_type":"random"}\n'
            os.write(master,b'ROM boot log\n'+b'x'*4500+b'\n'+observation[:35]);await asyncio.sleep(.1);os.write(master,observation[35:])
            await until(lambda:len(rt.store.devices(time.time()))==1)
            assert rt.invalid>=2;assert rt.snapshot()['stats']['observations']['ble']==1
            os.close(master);master=None
            await until(lambda:not rt.connected)
            master2,slave2=pty.openpty();tty.setraw(slave2);rt.settings.port=os.ttyname(slave2)
            await until(lambda:rt.connected)
            os.write(master2,(json.dumps({**status,'boot_id':124})+'\n').encode())
            await until(lambda:rt.status.get('boot_id')==124)
            os.close(master2);os.close(slave2)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await task
            if master is not None:os.close(master)
            os.close(slave);rt.store.db.close()
    asyncio.run(run())
