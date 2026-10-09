package com.example.app

import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // Mantiene la pantalla encendida durante el recorrido: algunos
        // fabricantes (Honor/Huawei) retrasan el GPS con la pantalla apagada.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "movimiento/pantalla")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "mantenerEncendida" -> {
                        if (call.arguments == true) {
                            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        } else {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        }
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
