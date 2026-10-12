Kısa Metin Sınıflandırmada Veri Artırmanın Etkisi: Müşteri Şikâyetleri Üzerine Bir Çalışma

ÖZET

Müşteri hizmetleri ekipleri her gün binlerce kısa şikâyet metnini doğru birime yönlendirmek zorundadır. Bu çalışmada, az sayıda etiketli örnek bulunan sınıflarda basit veri artırma tekniklerinin sınıflandırma başarısına etkisini inceledik. Bir telekomünikasyon şirketinden alınan ve kişisel bilgileri çıkarılmış 18.000 şikâyet metni üzerinde, eş anlamlı kelime değiştirme, rastgele kelime silme ve geri çeviri yöntemlerini karşılaştırdık. Değerlendirme, eğitimde hiç kullanılmamış iki aylık bir zaman diliminde yapıldı. Az örnekli sınıflarda geri çeviri, makro F1 skorunu 0,61'den 0,68'e yükseltti; diğer iki yöntem ise anlamlı bir fark yaratmadı. Çok örnekli sınıflarda hiçbir yöntem başarıyı artırmadı ve rastgele silme bir sınıfta başarıyı düşürdü. Sonuçlar, veri artırmanın her sınıfa değil yalnızca az örnekli sınıflara uygulanması gerektiğini ve geri çevirinin bu sınıflar için en güvenilir seçenek olduğunu göstermektedir. Ayrıca zaman içinde değişen şikâyet konularının, artırılmış verinin faydasını sınırladığını gözlemledik.

1. Giriş

Kısa metin sınıflandırma, müşteri hizmetlerinde en çok kullanılan doğal dil işleme uygulamalarından biridir (Yılmaz ve Demir, 2021). Ancak gerçek veri setlerinde sınıflar dengesizdir: fatura itirazı gibi konular binlerce örnek içerirken, numara taşıma gibi konular yalnızca birkaç yüz örnekle temsil edilir (Kaya vd., 2020).

Veri artırma, az örnekli sınıflar için yeni eğitim örnekleri üretmenin ucuz bir yoludur (Wei ve Zou, 2019). Bu yöntemlerin İngilizce metinlerde işe yaradığı gösterilmiş olsa da Türkçe gibi eklemeli dillerde etkileri daha az çalışılmıştır (Arslan, 2022).

Bu çalışmanın katkısı, üç yaygın veri artırma yöntemini gerçek ve zamana göre ayrılmış bir Türkçe veri setinde karşılaştırmak ve hangi sınıflarda işe yaradıklarını ayrı ayrı raporlamaktır.

2. Yöntem

Veri seti, on iki şikâyet sınıfına ayrılmış 18.000 metinden oluşmaktadır. Metinlerin ilk on ayı eğitim, sonraki iki ayı ise test için kullanıldı. Böylece model, eğitimde görmediği dönemlere ait şikâyetlerle değerlendirildi. Sınıfların örnek sayıları Tablo 1'de verilmiştir.

Tablo 1: Sınıflara göre eğitim ve test örneği sayıları.

Sınıflandırıcı olarak önceden eğitilmiş bir Türkçe dil modeli kullanıldı ve tüm deneylerde aynı ayarlar korundu. Her veri artırma yöntemi, yalnızca eğitim kümesindeki az örnekli sınıflara uygulandı ve her az örnekli sınıf için örnek sayısı iki katına çıkarıldı. Geri çeviri için metinler İngilizceye çevrilip tekrar Türkçeye çevrildi (Wei ve Zou, 2019).

3. Bulgular

Az örnekli sınıflarda geri çeviri, makro F1 skorunu 0,61'den 0,68'e yükseltti. Eş anlamlı kelime değiştirme ve rastgele silme ise 0,01'den küçük farklar üretti. Sınıf bazındaki sonuçlar Şekil 1'de gösterilmiştir.

Şekil 1: Az örnekli sınıflarda yöntemlere göre F1 skorları.

Çok örnekli sınıflarda hiçbir yöntem başarıyı artırmadı. Rastgele silme, kısa metinlerden oluşan "hat iptali" sınıfında F1 skorunu 0,04 düşürdü; bu sınıftaki metinler zaten çok kısa olduğu için silinen kelimeler anlamı bozuyordu.

4. Tartışma

Sonuçlarımız, veri artırmanın genel bir çözüm değil, az örnekli sınıflar için hedefli bir araç olarak kullanılması gerektiğini göstermektedir. Geri çevirinin daha başarılı olması, cümle yapısını değiştirirken anlamı korumasıyla açıklanabilir.

Çalışmanın temel sınırlılığı, verinin tek bir şirketten gelmesidir. Ayrıca test dönemindeki yeni şikâyet konuları, artırılmış verinin faydasını sınırlamıştır. Gelecek çalışmalarda farklı sektörlerden veri setleri kullanılması planlanmaktadır.

KAYNAKÇA

Arslan, B. (2022). Eklemeli dillerde metin sınıflandırma için veri artırma. Bilişim Teknolojileri Dergisi, 15(2), 101-112.
Kaya, E., Şahin, M. ve Öztürk, C. (2020). Müşteri şikâyetlerinin otomatik sınıflandırılması. Yönetim Bilişim Sistemleri Dergisi, 6(1), 33-47.
Wei, J. ve Zou, K. (2019). Easy data augmentation techniques for boosting performance on text classification tasks. Proceedings of EMNLP-IJCNLP, 6382-6388.
Yılmaz, A. ve Demir, S. (2021). Türkçe kısa metinlerde sınıflandırma yöntemlerinin karşılaştırılması. Mühendislik Bilimleri Dergisi, 27(4), 512-520.
