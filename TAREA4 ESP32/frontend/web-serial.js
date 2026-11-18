(() => {
  const button = document.querySelector('#usbConnect');
  const message = document.querySelector('#usbMessage');
  const encoder = new TextEncoder();
  let disconnect;

  async function connect() {
    button.disabled = true;
    let port, reader, writer, socket, opened;
    let writes = Promise.resolve();
    let stopped = false;
    let reason = 'ESP32 desconectado.';
    const stop = (text) => {
      if (stopped) return;
      stopped = true;
      reason = text;
      button.disabled = true;
      if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
      if (reader) reader.cancel().catch(() => {});
    };
    try {
      port = await navigator.serial.requestPort();
      await port.open({baudRate: 115200});
      opened = true;
      reader = port.readable.getReader();
      writer = port.writable.getWriter();
      socket = new WebSocket('wss://' + location.host + '/api/browser-usb');
      await new Promise((resolve, reject) => {
        socket.onmessage = event => {
          if (JSON.parse(event.data).ready) resolve();
        };
        socket.onclose = socket.onerror = () => reject(new Error('EC2 rechazó la conexión. Comprueba si otra pestaña ya usa el detector.'));
      });
      socket.onclose = socket.onerror = () => stop('Se perdió la conexión con EC2. Vuelve a conectar.');
      socket.onmessage = event => {
        const {command} = JSON.parse(event.data);
        writes = writes.then(() => writer.write(encoder.encode(JSON.stringify(command) + '\n')))
          .catch(() => stop('Falló la escritura al ESP32.'));
      };
      disconnect = () => stop('ESP32 desconectado.');
      button.textContent = 'Desconectar ESP32';
      button.disabled = false;
      message.textContent = 'USB conectado';
      while (!stopped) {
        const {done, value} = await reader.read();
        if (done || stopped) break;
        for (let offset = 0; offset < value.length; offset += 16384) {
          if (socket.bufferedAmount > 262144) throw new Error('La conexión con EC2 está saturada. Vuelve a conectar.');
          socket.send(value.subarray(offset, offset + 16384));
        }
      }
    } catch (error) {
      reason = error.name === 'NotFoundError' ? 'Selección cancelada.' : error.message;
    } finally {
      stop(reason);
      if (writer) {
        await writer.abort().catch(() => {});
        await writes;
        writer.releaseLock();
      }
      if (reader) reader.releaseLock();
      if (opened) await port.close().catch(() => {});
      message.textContent = reason;
      disconnect = undefined;
      button.textContent = 'Conectar ESP32';
      button.disabled = false;
    }
  }
  if (!window.isSecureContext || !navigator.serial) {
    button.disabled = true;
    message.textContent = 'Abre el panel por HTTPS en Chrome o Edge de escritorio.';
  } else {
    button.onclick = () => disconnect ? disconnect() : connect();
  }
})();
