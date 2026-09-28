package com.niyamdrishti.app;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Point;
import android.graphics.Rect;
import android.util.Base64;
import android.util.Log;

import androidx.annotation.NonNull;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.barcode.BarcodeScanner;
import com.google.mlkit.vision.barcode.BarcodeScanning;
import com.google.mlkit.vision.barcode.BarcodeScannerOptions;
import com.google.mlkit.vision.barcode.common.Barcode;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.util.List;

/**
 * Android-only bridge for the bundled ML Kit Latin text recognizer.
 *
 * The web layer supplies the already-normalized upright JPEG used everywhere
 * else in NiyamDrishti. Every returned region is therefore expressed directly
 * in that same source-image pixel coordinate space; this plugin deliberately
 * performs OCR only and never assigns a statutory-field label or verdict.
 */
@CapacitorPlugin(name = "OfflineOcr")
public class OfflineOcrPlugin extends Plugin {
    private TextRecognizer recognizer;
    private BarcodeScanner barcodeScanner;

    @Override
    public void load() {
        recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        BarcodeScannerOptions barcodeOptions = new BarcodeScannerOptions.Builder()
            .setBarcodeFormats(
                Barcode.FORMAT_EAN_13,
                Barcode.FORMAT_EAN_8,
                Barcode.FORMAT_UPC_A,
                Barcode.FORMAT_UPC_E,
                Barcode.FORMAT_CODE_128,
                Barcode.FORMAT_CODE_39,
                Barcode.FORMAT_CODE_93,
                Barcode.FORMAT_ITF,
                Barcode.FORMAT_CODABAR
            )
            .build();
        barcodeScanner = BarcodeScanning.getClient(barcodeOptions);
        Log.i("NiyamOfflineOcr", "Bundled ML Kit Latin recognizer loaded");
    }

    @PluginMethod
    public void isAvailable(PluginCall call) {
        JSObject result = new JSObject();
        result.put("available", recognizer != null);
        result.put("script", "latin");
        result.put("mode", "bundled");
        call.resolve(result);
    }

    @PluginMethod
    public void recognize(PluginCall call) {
        if (recognizer == null) {
            call.reject("Offline OCR is not initialized.");
            return;
        }

        String dataUrl = call.getString("dataUrl");
        Bitmap bitmap = decodeDataUrl(dataUrl);
        if (bitmap == null) {
            call.reject("Offline OCR requires a valid base64 image data URL.");
            return;
        }

        InputImage image = InputImage.fromBitmap(bitmap, 0);
        recognizer.process(image)
            .addOnSuccessListener(text -> call.resolve(serialize(text, bitmap.getWidth(), bitmap.getHeight())))
            .addOnFailureListener(error -> call.reject("Offline OCR could not read this image.", error));
    }

    @PluginMethod
    public void isBarcodeAvailable(PluginCall call) {
        JSObject result = new JSObject();
        result.put("available", barcodeScanner != null);
        result.put("mode", "bundled");
        call.resolve(result);
    }

    /** Returns only decoded barcode data and source-image geometry, never a verdict. */
    @PluginMethod
    public void recognizeBarcodes(PluginCall call) {
        if (barcodeScanner == null) {
            call.reject("Offline barcode scanner is not initialized.");
            return;
        }
        Bitmap bitmap = decodeDataUrl(call.getString("dataUrl"));
        if (bitmap == null) {
            call.reject("Offline barcode scanning requires a valid base64 image data URL.");
            return;
        }
        InputImage image = InputImage.fromBitmap(bitmap, 0);
        barcodeScanner.process(image)
            .addOnSuccessListener(barcodes -> call.resolve(serializeBarcodes(barcodes, bitmap.getWidth(), bitmap.getHeight())))
            .addOnFailureListener(error -> call.reject("Offline barcode scanning could not read this image.", error));
    }

    private Bitmap decodeDataUrl(String dataUrl) {
        if (dataUrl == null) {
            return null;
        }
        int comma = dataUrl.indexOf(',');
        if (comma < 0 || !dataUrl.substring(0, comma).contains(";base64")) {
            return null;
        }
        try {
            byte[] bytes = Base64.decode(dataUrl.substring(comma + 1), Base64.DEFAULT);
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    @NonNull
    private JSObject serialize(Text text, int sourceWidth, int sourceHeight) {
        JSObject result = new JSObject();
        result.put("text", text.getText());
        result.put("sourceWidth", sourceWidth);
        result.put("sourceHeight", sourceHeight);

        JSArray lines = new JSArray();
        for (Text.TextBlock block : text.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                Rect rectangle = line.getBoundingBox();
                if (rectangle == null || rectangle.width() <= 0 || rectangle.height() <= 0) {
                    continue;
                }

                JSObject item = new JSObject();
                item.put("text", line.getText());
                item.put("boundingBox", box(rectangle, line.getCornerPoints()));
                lines.put(item);
            }
        }
        result.put("lines", lines);
        return result;
    }

    @NonNull
    private JSObject serializeBarcodes(List<Barcode> barcodes, int sourceWidth, int sourceHeight) {
        JSObject result = new JSObject();
        result.put("sourceWidth", sourceWidth);
        result.put("sourceHeight", sourceHeight);
        JSArray items = new JSArray();
        for (Barcode barcode : barcodes) {
            String rawValue = barcode.getRawValue();
            Rect rectangle = barcode.getBoundingBox();
            if (rawValue == null || rawValue.isEmpty() || rectangle == null
                || rectangle.width() <= 0 || rectangle.height() <= 0) {
                continue;
            }
            JSObject item = new JSObject();
            item.put("rawValue", rawValue);
            item.put("displayValue", barcode.getDisplayValue());
            item.put("format", barcode.getFormat());
            item.put("boundingBox", box(rectangle, barcode.getCornerPoints()));
            items.put(item);
        }
        result.put("barcodes", items);
        return result;
    }

    @NonNull
    private JSObject box(Rect rectangle, Point[] corners) {
        JSObject box = new JSObject();
        box.put("x", rectangle.left);
        box.put("y", rectangle.top);
        box.put("w", rectangle.width());
        box.put("h", rectangle.height());
        box.put("coordinateSpace", "source_image_px");

        JSArray polygon = new JSArray();
        if (corners != null && corners.length == 4) {
            for (Point corner : corners) {
                polygon.put(point(corner.x, corner.y));
            }
        } else {
            polygon.put(point(rectangle.left, rectangle.top));
            polygon.put(point(rectangle.right, rectangle.top));
            polygon.put(point(rectangle.right, rectangle.bottom));
            polygon.put(point(rectangle.left, rectangle.bottom));
        }
        box.put("polygon", polygon);
        return box;
    }

    @NonNull
    private JSArray point(int x, int y) {
        JSArray point = new JSArray();
        point.put(x);
        point.put(y);
        return point;
    }
}
