/// Detector de pasos (podómetro) a partir del acelerómetro.
///
/// Caminar produce picos de aceleración rítmicos (1.2-2.8 pasos/s). Agarrar,
/// girar o mover el teléfono en la mano produce picos sueltos o irregulares.
/// Solo se confirma que la persona camina tras varios picos con ritmo de
/// paso; los picos aislados no cuentan.
class DetectorPasos {
  DetectorPasos({
    this.umbralPico = 1.0,
    this.intervaloMinMs = 300,
    this.intervaloMaxMs = 1100,
    this.pasosParaConfirmar = 3,
    this.toleranciaRitmo = 0.45,
  });

  /// Altura mínima del pico sobre la gravedad (m/s²).
  final double umbralPico;

  /// Separación válida entre pasos consecutivos.
  final int intervaloMinMs;
  final int intervaloMaxMs;

  /// Pasos con ritmo regular necesarios para afirmar que se camina.
  final int pasosParaConfirmar;

  /// Variación máxima permitida entre intervalos consecutivos (proporción).
  final double toleranciaRitmo;

  double? _gravedad;
  double _suavizada = 0;
  bool _armado = true;
  int? _ultimoPicoMs;
  int? _ultimoIntervaloMs;
  int _candidatos = 0;
  int _pasosTotales = 0;
  bool _caminando = false;

  /// Pasos confirmados desde que se creó o reinició el detector.
  int get pasosTotales => _pasosTotales;

  /// true mientras se detecta una marcha (el último paso fue hace poco).
  bool caminando(int ahoraMs) =>
      _caminando &&
      _ultimoPicoMs != null &&
      ahoraMs - _ultimoPicoMs! <= intervaloMaxMs + 400;

  void reiniciar() {
    _gravedad = null;
    _suavizada = 0;
    _armado = true;
    _ultimoPicoMs = null;
    _ultimoIntervaloMs = null;
    _candidatos = 0;
    _pasosTotales = 0;
    _caminando = false;
  }

  /// Procesa una muestra del acelerómetro (módulo con gravedad, m/s²).
  /// Devuelve la cantidad de pasos nuevos confirmados (0 normalmente).
  int procesar(double modulo, int tiempoMs) {
    // Gravedad estimada con un filtro muy lento; señal suavizada para
    // eliminar la vibración de alta frecuencia.
    _gravedad = _gravedad == null ? modulo : _gravedad! * 0.98 + modulo * 0.02;
    _suavizada = _suavizada * 0.6 + (modulo - _gravedad!) * 0.4;

    // Se rearma al volver por debajo de la gravedad (un pico por paso).
    if (_suavizada < 0) _armado = true;
    if (!_armado || _suavizada < umbralPico) {
      if (_caminando && !caminando(tiempoMs)) _terminarMarcha();
      return 0;
    }
    _armado = false;

    final anterior = _ultimoPicoMs;
    _ultimoPicoMs = tiempoMs;
    if (anterior == null) {
      _candidatos = 1;
      return 0;
    }
    final intervalo = tiempoMs - anterior;
    final ritmoValido = intervalo >= intervaloMinMs &&
        intervalo <= intervaloMaxMs &&
        (_ultimoIntervaloMs == null ||
            (intervalo - _ultimoIntervaloMs!).abs() <=
                _ultimoIntervaloMs! * toleranciaRitmo);
    _ultimoIntervaloMs = intervalo;

    if (!ritmoValido) {
      // Pico irregular (manipular el teléfono): se reinicia la cuenta.
      _terminarMarcha();
      _candidatos = 1;
      return 0;
    }
    _candidatos++;
    if (_caminando) {
      _pasosTotales++;
      return 1;
    }
    if (_candidatos >= pasosParaConfirmar) {
      // Marcha confirmada: se cuentan también los pasos candidatos.
      _caminando = true;
      _pasosTotales += _candidatos;
      return _candidatos;
    }
    return 0;
  }

  void _terminarMarcha() {
    _caminando = false;
    _candidatos = 0;
    _ultimoIntervaloMs = null;
  }
}
