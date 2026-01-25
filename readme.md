# 🌍 ATLAS WEB ASİSTAN

Bu proje, gelişmiş yapay zeka modellerini (Llama 3, Stable Diffusion) kullanarak çalışan sesli ve görsel bir asistandır.

## 📋 Gereksinimler

Kuruluma başlamadan önce bilgisayarınızda şunların yüklü olduğundan emin olun:

1.  **Python 3.10+** (Yüklerken "Add to PATH" işaretlemeyi unutmayın!)
2.  **Git**
3.  **Node.js** (Web arayüzü için)

---

## 🚀 Hızlı Kurulum

### Adım 1: Projeyi İndirin
Terminali açın ve projeyi masaüstüne (veya istediğiniz yere) indirin:
```bash
git clone https://github.com/KULLANICI_ADI/Ses_Asistani.git
cd Ses_Asistani
```

### Adım 2: Otomatik Kurulumu Başlatın
Sanal ortamı oluşturmak, gerekli kütüphaneleri yüklemek ve yapay zeka modellerini indirmek için şu komutu çalıştırın:

```cmd
python install.py
```
*(Bu işlem internet hızınıza bağlı olarak zaman alabilir. Lütfen bitmesini bekleyin.)*

### Adım 3: Frontend Paketlerini Yükleyin
Web arayüzünün çalışması için frontend paketlerini bir kez yüklemeniz gerekir:

```cmd
cd web/frontend
npm install
cd ../..
```

---

## ▶️ Başlatma

Atlas'ı başlatmak için tek yapmanız gereken:

```cmd
python run.py
```

Bu komut:
1.  Backend'i (Beyin) başlatır.
2.  Frontend'i (Arayüz) başlatır.
3.  Tarayıcınızı otomatik açar.

Çıkmak için terminalde `CTRL+C` yapmanız yeterlidir.

---

### Manuel Başlatma (Geliştiriciler İçin)
Eğer ayrı ayrı görmek isterseniz:

---

## ❓ Sorun Giderme

-   **"python bulunamadı" hatası:** Python'u kurarken "Add to PATH" seçeneğini işaretlediğinizden emin olun.
-   **Stable Diffusion hatası:** İlk kurulumda modelin (6GB) inmesi gerekebilir, internet bağlantınızı kontrol edin.
-   **Ses gelmiyor:** Hoparlör sesini kontrol edin ve tarayıcı izinlerini verin.