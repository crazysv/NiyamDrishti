package com.niyamdrishti.app;

import android.os.Bundle;
import android.util.Log;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        Log.i("NiyamOfflineOcr", "Registering OfflineOcr Capacitor bridge");
        registerPlugin(OfflineOcrPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
