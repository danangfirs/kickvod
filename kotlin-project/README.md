# Laporan Proyek Aplikasi Android - Retrofit & REST API

## A. Tujuan

Aplikasi ini dibuat untuk memenuhi tujuan pembelajaran berikut:

- Menggunakan library Retrofit untuk berkomunikasi dengan REST API.
- Mengambil data dari API melalui GET request.
- Mengirim data baru ke API melalui POST request.
- Menampilkan daftar data menggunakan RecyclerView.
- Mengintegrasikan Antarmuka Pengguna (UI) dengan proses request API.
- Menangani kondisi galat (error) seperti koneksi gagal atau input tidak valid untuk memastikan stabilitas aplikasi.

---

## B. Penjelasan Alur Kerja Aplikasi

Aplikasi ini adalah sebuah klien REST API sederhana yang berinteraksi dengan API publik **JSONPlaceholder** (`https://jsonplaceholder.typicode.com/`).

*Catatan: Teks konten (judul dan isi post) yang ditampilkan dalam aplikasi adalah teks placeholder "Lorem Ipsum" yang disediakan langsung oleh API. Teks ini bukan merupakan bagian dari aplikasi dan hanya berfungsi sebagai data contoh.*

### 1. Arsitektur dan Komponen Kunci

- **`RetrofitClient.kt`**: Objek tunggal (*singleton*) yang mengonfigurasi dan membuat instance Retrofit. Ini adalah pusat dari semua permintaan API, dengan Base URL dan Gson Converter yang sudah diatur.
- **`ApiService.kt`**: *Interface* yang mendefinisikan *endpoint* API. Terdapat dua metode: `getPosts()` untuk `GET /posts` dan `createPost()` untuk `POST /posts`.
- **`Post.kt`**: Sebuah `data class` Kotlin yang merepresentasikan struktur data dari sebuah *post*, termasuk `userId`, `id`, `title`, dan `body`. Ini digunakan oleh Gson untuk mem-parsing JSON.
- **`MainActivity.kt`**: *Activity* utama yang mengatur UI, menginisialisasi RecyclerView, dan menangani logika untuk mengambil (*fetch*) dan mengirim (*create*) data.
- **`PostAdapter.kt`**: *Adapter* untuk `RecyclerView` yang bertanggung jawab untuk mengambil daftar `Post` dan menampilkannya sebagai item-item di UI.
- **Layouts**:
  - `activity_main.xml`: Tampilan utama yang berisi `RecyclerView` untuk menampilkan daftar post dan `FloatingActionButton` untuk menambah post baru.
  - `item_post.xml`: Layout untuk satu item dalam RecyclerView, yang menampilkan *title* dan *body* dari sebuah post.
  - `dialog_add_post.xml`: Layout untuk form input yang muncul dalam sebuah `AlertDialog` saat pengguna ingin menambah post baru.

### 2. Alur Pengambilan Data (GET Request)

1.  **Inisialisasi**: Saat `MainActivity` pertama kali dibuat (`onCreate`), fungsi `fetchPosts()` langsung dipanggil.
2.  **Permintaan API**: `fetchPosts()` menggunakan `RetrofitClient.instance` untuk memanggil metode `getPosts()`. Permintaan ini dijalankan secara *asynchronous* menggunakan `enqueue()`.
3.  **Menampilkan Indikator Loading**: Selama permintaan berjalan, sebuah `ProgressBar` akan ditampilkan untuk memberi tahu pengguna bahwa data sedang dimuat.
4.  **Menangani Respons**:
    - **Jika Berhasil (`onResponse`)**: Data `List<Post>` yang diterima dari server akan diteruskan ke `PostAdapter` melalui metode `updateData()`. Adapter kemudian memperbarui `RecyclerView` untuk menampilkan daftar post.
    - **Jika Gagal (`onFailure`)**: Jika terjadi masalah koneksi (misalnya, tidak ada internet), sebuah pesan `Toast` akan ditampilkan untuk memberi tahu pengguna tentang masalah jaringan.

### 3. Alur Pengiriman Data (POST Request)

1.  **Input Pengguna**: Pengguna menekan `FloatingActionButton` (+) di `MainActivity`.
2.  **Menampilkan Form**: Sebuah `AlertDialog` yang berisi form input (`dialog_add_post.xml`) ditampilkan. Pengguna diminta untuk mengisi *User ID*, *Title*, dan *Body*.
3.  **Validasi Input**: Setelah pengguna menekan tombol "Post", aplikasi akan memvalidasi input. Jika ada kolom yang kosong atau User ID tidak valid, sebuah pesan `Toast` akan muncul dan proses pengiriman dibatalkan.
4.  **Permintaan API**: Jika input valid, sebuah objek `Post` baru akan dibuat dan dikirim ke server melalui metode `createPost()` dari `ApiService`. Permintaan ini juga berjalan secara *asynchronous*.
5.  **Menangani Respons**:
    - **Jika Berhasil (`onResponse`)**: Sebuah `Toast` akan ditampilkan untuk mengonfirmasi bahwa post berhasil dibuat. Setelah itu, aplikasi akan otomatis memanggil `fetchPosts()` lagi untuk menyegarkan daftar data di `RecyclerView`.
    - **Jika Gagal (`onFailure` atau `response.isSuccessful` bernilai `false`)**: Pesan galat akan ditampilkan melalui `Toast` untuk menginformasikan pengguna bahwa post gagal dibuat.

### 4. Penanganan Galat (Error Handling)

Aplikasi ini menerapkan beberapa mekanisme penanganan galat untuk menjaga stabilitas:

- **Koneksi Gagal**: *Callback* `onFailure` dari Retrofit akan menangkap galat jaringan dan menampilkan pesan kepada pengguna.
- **Input Tidak Valid**: Validasi sederhana memastikan semua kolom form diisi sebelum mengirim data.
- **Respons Server Gagal**: Aplikasi memeriksa `response.isSuccessful`. Jika server mengembalikan kode galat (misal, 404 atau 500), pesan yang sesuai akan ditampilkan.

Dengan alur kerja ini, aplikasi dapat berfungsi secara stabil dan memberikan umpan balik yang jelas kepada pengguna dalam berbagai skenario.

---

## C. Tangkapan Layar (Screenshot) Aplikasi

Berikut adalah tangkapan layar dari aplikasi saat berjalan.

![Tampilan Utama Aplikasi](https://storage.googleapis.com/aiex-shared-images/51e3381a-4712-4ebc-9e2c-b5f778688755.png)
