FROM python:3.11-slim-bookworm

WORKDIR /app

# System deps for OpenCV + WeasyPrint + zxing-cpp + Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info libffi-dev \
    tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV FLAGS_allocator_strategy=naive_best_fit
ENV FLAGS_fraction_of_gpu_memory_to_use=0.0
ENV FLAGS_eager_delete_tensor_gb=0.0

EXPOSE 8000 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
