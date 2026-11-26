# Servidor HTTP SOLO para el archivo HTML (NO accede al COM, NO es puente USB).
# Windows PowerShell incluido en Windows 10/11. URL local, no internet.
$ErrorActionPreference = 'Stop'
$port = 18763
$uri = "http://127.0.0.1:$port/"
$htmlPath = Join-Path $PSScriptRoot 'index.html'
$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse('127.0.0.1'), $port)
try { $listener.Start() }
catch {
  Write-Host "No se pudo iniciar el panel: puerto $port en uso. Cierra otra ventana del panel." -ForegroundColor Red
  Read-Host 'Presiona Enter para cerrar'
  exit 1
}
Write-Host "PANEL ESP32-CAM LISTO: $uri" -ForegroundColor Green
Write-Host 'Deja esta ventana abierta mientras uses el HTML. Cierra el Monitor Serie de Arduino.'
Write-Host 'Conecta desde Chrome o Edge, elige tu COM (no esta fijado).'
try { Start-Process $uri } catch { Write-Host "Abre Chrome o Edge y escribe: $uri" }
try {
  while ($true) {
    $client = $listener.AcceptTcpClient()
    try {
      $client.ReceiveTimeout = 4000
      $client.SendTimeout = 4000
      $stream = $client.GetStream()
      $buffer = New-Object byte[] 4096
      $n = $stream.Read($buffer, 0, $buffer.Length)
      if ($n -le 0) { continue }
      $request = [System.Text.Encoding]::ASCII.GetString($buffer,0,$n)
      $first = ($request -split "`r?`n")[0]
      if ($first -match '^GET (/|/index\.html)(\?.*)? HTTP/') {
        $body = [System.IO.File]::ReadAllBytes($htmlPath)
        $status = 'HTTP/1.1 200 OK'
        $contentType = 'text/html; charset=utf-8'
      } else {
        $body = [System.Text.Encoding]::UTF8.GetBytes('Not found')
        $status = 'HTTP/1.1 404 Not Found'
        $contentType = 'text/plain; charset=utf-8'
      }
      $headers = "$status`r`nContent-Type: $contentType`r`nContent-Length: $($body.Length)`r`nCache-Control: no-store`r`nConnection: close`r`nX-Content-Type-Options: nosniff`r`n`r`n"
      $headBytes = [System.Text.Encoding]::ASCII.GetBytes($headers)
      $stream.Write($headBytes, 0, $headBytes.Length)
      $stream.Write($body, 0, $body.Length)
      $stream.Flush()
    } catch { Write-Host "Solicitud web no completada: $($_.Exception.Message)" }
    finally { $client.Close() }
  }
} finally { $listener.Stop() }
