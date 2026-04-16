# ============================================================
# BASIC Dockerfile — Single-stage, dễ đọc, dễ hiểu
# Dùng làm điểm khởi đầu trước khi học multi-stage
# ============================================================

# Bước 1: Chọn base image
# python:3.11 = full Python distribution (~1 GB)
FROM python:3.11

# Bước 2: Đặt working directory trong container
WORKDIR /app

# Bước 3: Copy requirements TRƯỚC (Docker layer cache)
# Lý do: nếu chỉ thay đổi code (không đổi deps),
# Docker sẽ reuse layer này → build nhanh hơn
COPY requirements.txt .

# Bước 4: Cài dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Bước 5: Copy code vào container
COPY app.py .

# Bước 6: Copy mock utils
COPY ../../utils/mock_llm.py /app/utils/mock_llm.py

# Bước 7: Expose port để documentation (không bắt buộc)
EXPOSE 8000

# Bước 8: Command mặc định khi container start
CMD ["python", "app.py"]

# ============================================================
# Để build và chạy:
#   docker build -t agent-basic .
#   docker run -p 8000:8000 agent-basic
#   curl http://localhost:8000/health
# ============================================================
