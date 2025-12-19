# Implementasi Sistem Event Aggregator Terdistribusi

Proyek ini adalah implementasi sistem aggregator event terdistribusi yang dirancang untuk menerima, memproses, dan menyimpan volume data yang besar dengan efisien. Sistem ini dibangun dengan arsitektur berbasis layanan (microservices) menggunakan Docker, Python (FastAPI), dan PostgreSQL.

## Arsitektur Sistem

Sistem ini terdiri dari beberapa komponen utama yang bekerja sama:

1.  **Publisher (`publisher`)**:
    *   Sebuah skrip Python yang bertugas untuk mensimulasikan pengiriman event dalam jumlah besar.
    *   Secara sengaja mengirimkan event duplikat untuk menguji kemampuan deduplikasi sistem.
    *   Berkomunikasi dengan `Aggregator` melalui HTTP POST request.

2.  **Aggregator (`aggregator`)**:
    *   Inti dari sistem, berupa API service yang dibangun menggunakan FastAPI.
    *   Menerima event dari `Publisher` melalui endpoint `/publish`.
    *   Melakukan validasi, deduplikasi, dan menyimpan event unik ke dalam database.
    *   Menyediakan endpoint untuk memantau statistik (`/stats`) dan melihat event terbaru (`/events`).

3.  **Storage (`storage`)**:
    *   Database PostgreSQL yang berfungsi sebagai tempat penyimpanan event yang sudah diproses.
    *   Skema database dirancang untuk menangani deduplikasi secara efisien menggunakan *composite primary key*.

4.  **Broker (`broker`)**:
    *   Layanan Redis yang disediakan untuk potensi pengembangan di masa depan (misalnya, sebagai message queue untuk antrian event), meskipun saat ini tidak terintegrasi secara aktif dalam alur utama.

5.  **Network (`internal_net`)**:
    *   Semua layanan berjalan di dalam jaringan Docker internal yang terisolasi, memastikan komunikasi yang aman dan cepat antar komponen.


## Cara Menjalankan (Build/Run)

Sistem ini dirancang untuk dijalankan menggunakan Docker dan Docker Compose.

**Prasyarat:**
*   Docker Engine
*   Docker Compose

**Langkah-langkah:**

1.  **Build Image & Jalankan Kontainer:**
    Buka terminal di direktori root proyek dan jalankan perintah berikut. Perintah ini akan membangun image untuk `aggregator` dan `publisher`, lalu menjalankan semua layanan di background.

    ```bash
    docker-compose up --build -d
    ```

2.  **Memulai Simulasi Publisher:**
    Setelah semua kontainer berjalan, `publisher` akan secara otomatis memulai simulasi pengiriman 20.000 event ke `aggregator`. Proses ini dapat dipantau melalui log.


3.  **Memantau Aggregator:**
    Anda dapat melihat log dari `aggregator` untuk memantau proses penerimaan event dan penanganan duplikat.

    ```bash
    docker-compose logs -f aggregator
    ```

4.  **Menghentikan Sistem:**
    Untuk menghentikan semua layanan dan menghapus kontainer, jalankan:

    ```bash
    docker-compose down
    ```

## Deskripsi Endpoints

Endpoint API disediakan oleh layanan **aggregator** yang berjalan di `http://localhost:8000`.

---

### `POST /publish`

Menerima dan memproses satu event. Endpoint ini adalah tujuan utama dari `publisher`.

*   **Request Body**:
    ```json
    {
        "topic": "string",
        "event_id": "string",
        "timestamp": "string (ISO 8601 format)",
        "source": "string",
        "payload": {
            "key": "value"
        }
    }
    ```

*   **Responses**:
    *   `200 OK`: Jika event berhasil diproses (`{"status": "success", ...}`).
    *   `200 OK`: Jika event duplikat terdeteksi dan diabaikan (`{"status": "ignored", ...}`).
    *   `422 Unprocessable Entity`: Jika body request tidak valid (misalnya, field wajib hilang atau tipe data salah).

---

### `GET /stats`

Mengembalikan statistik operasional dari aggregator.

*   **Response Body**:
    ```json
    {
        "received": "integer",          // Total event yang diterima (unik + duplikat)
        "unique_processed": "integer",  // Jumlah event unik yang berhasil disimpan
        "duplicate_dropped": "integer", // Jumlah event duplikat yang ditolak
        "topics_active": "integer",     // Jumlah topik unik yang telah diproses
        "uptime_seconds": "float"       // Waktu berjalan service dalam detik
    }
    ```

---

### `GET /events`

Mengambil daftar event terakhir yang berhasil diproses dari database.

*   **Query Parameters**:
    *   `limit` (opsional): Jumlah event yang ingin ditampilkan. Default: `10`.

*   **Response Body**: Array dari objek event.
    ```json
    [
        {
            "topic": "user_login",
            "event_id": "some-uuid",
            "timestamp": "2025-12-19T12:00:00Z",
            "source": "pytest",
            "payload": {"test": "data"},
            "created_at": "2025-12-19T12:01:00Z"
        },
        ...
    ]
    ```

## Asumsi & Desain

*   **Deduplikasi**: Logika deduplikasi diimplementasikan pada level database menggunakan *Composite Primary Key* pada kolom `(topic, event_id)`. Ini adalah pendekatan yang sangat efisien dan aman dari *race condition* dibandingkan jika deduplikasi dicek di level aplikasi.
*   **Kinerja**: Aplikasi `aggregator` menggunakan `asyncpg` untuk berinteraksi dengan PostgreSQL secara asinkron, memberikan throughput yang tinggi di bawah beban kerja I/O-bound.
*   **Integritas Data**: `ON CONFLICT DO NOTHING` digunakan untuk menangani duplikat. Ini memastikan bahwa upaya penulisan data yang sama tidak menimbulkan error, melainkan diabaikan secara diam-diam. Counter di `audit_stats` kemudian di-update untuk keperluan monitoring.
*   **Skalabilitas**: Arsitektur ini dapat dikembangkan lebih lanjut. Misalnya, dengan menempatkan load balancer di depan beberapa instance `aggregator` atau menggunakan Redis (`broker`) sebagai *message queue* untuk menyerap lonjakan traffic.

## Cara Menjalankan Test

Proyek ini dilengkapi dengan serangkaian *integration test* yang memvalidasi fungsionalitas `aggregator`.

**Prasyarat:**
*   Pastikan sistem sedang berjalan (jalankan `docker-compose up -d`).
*   Python 3.10+ dan `pip` terinstall di local machine.
*   Virtual environment (dianjurkan).

**Langkah-langkah:**

1.  **Setup Environment (jika belum):**
    Buat dan aktifkan virtual environment.

    ```bash
    python -m venv venv
    source venv/Scripts/activate 
    ```

2.  **Install Dependencies:**
    Install `pytest` dan `requests` yang dibutuhkan untuk menjalankan test.

    ```bash
    pip install pytest requests
    ```

3.  **Jalankan Pytest:**
    Dari direktori root proyek, jalankan perintah `pytest`. Pytest akan secara otomatis menemukan dan menjalankan semua file tes.

    ```bash
    pytest -v
    ```

    Flag `-v` (verbose) akan menampilkan detail dari setiap tes yang dijalankan. Tes mencakup validasi endpoint, logika deduplikasi, *race condition*, dan integritas data.
