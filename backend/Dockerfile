# MediaPipe links against OpenGL ES even for headless CPU inference, and it
# depends on opencv-contrib-python (the non-headless build) regardless of
# what we pin. Render's native Python runtime has neither library and offers
# no way to install them, which surfaces as:
#
#   libGLESv2.so.2: cannot open shared object file
#
# So the backend runs as a container, where the system libraries can be
# installed explicitly.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Graphics and threading libraries MediaPipe and OpenCV load at runtime.
#   libgles2      -> libGLESv2.so.2   (the failure above)
#   libegl1       -> libEGL.so.1      (MediaPipe's GL context)
#   libgl1        -> libGL.so.1       (OpenCV)
#   libglib2.0-0  -> libgthread-2.0.so.0
#   libgomp1      -> OpenMP, used by OpenCV and scikit-learn
#   libsm6/libxext6/libxrender1 -> X11 stubs OpenCV still links
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgles2 \
        libegl1 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# dependencies first, so application edits do not invalidate the pip layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# screening records live outside the image; mount a disk here to persist them
ENV SCREENINGS_DB=/var/data/screenings.db
RUN mkdir -p /var/data

# Render supplies $PORT at runtime
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
