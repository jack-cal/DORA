# SUMUWW · 0.57.46 / 0.6.95

Düğüme ücret sorgusu, gönderim öncesi kontrol, RBF değiştirme durumu ve blok sırasıyla veri okuma eklendi. Bekleyen işlemler silinmeden önce yeni işlem doğrulanır. Çoklu imza ve kilitli çıktılar, yalıtılmış etkinleştirme testleri için uygulandı; genel ağda henüz etkin değildir.

1 SMW = 100.000.000 yugeon. Otomatik ücret, yerel gözlemlere göre üç seçenek sunar; onay süresini garanti etmez. yugeon/vB oranını elle girebilirsiniz. Göndermeden önce son ücreti ve toplamı SMW cinsinden kontrol edin. Reddedilen işlem bakiyeyi azaltmaz.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Otomatik ücret, bekleyen veri hacmini, blok kapasitesini ve işlem önceliğini dikkate alır. Geçmiş blokların ücretleri kullanılmaz. Kuyruk kısaysa asgari oran korunur. Önizleme yenilenir; son onay ücreti sabitler. Gözlemler tüm düğümleri değil, bağlı yerel düğümü kapsar.

Bu düğümün kaydettiği işlem değiştirme geçmişi, cüzdan yeniden başlatıldığında korunur. Kaldırılan işlemler bakiyeyi etkilemez.

Gezgin, açıklanmış çoklu imza ve çıktı kilidi koşullarını gösterir. Genel ağda etkinleştirme tarihi henüz belirlenmedi.


Madencilik geçmişi her bloğun yeni ihracını, işlem ücretlerini ve toplam ödülünü ayrı gösterir. Cüzdanınıza gelen tutar ayrıca gösterilir. Ödül kısmen talep edilmişse iki bileşenin dağılımı varsayılmaz. Düğüm, ücret tahmini dahil 28 RPC yöntemi sunar; imzalı işlemleri doğrular ve iletir.
