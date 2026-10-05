import json
import random
import re
import urllib.parse
import urllib.request
from collections import Counter
import streamlit as st

# =====================================================================
# 1. SAYFA YAPILANDIRMASI VE GELİŞMİŞ CSS STİLLERİ
# =====================================================================
st.set_page_config(
    page_title="AniZek — Gelişmiş Anime Platformu",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }
    
    .profile-card {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .post-box {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 15px;
    }
    
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)


# =====================================================================
# 2. SESSION STATE BAŞLANGIÇLARI (VERİ TABANI & HAFIZA)
# =====================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = True

if "username" not in st.session_state:
    st.session_state.username = "tah_emir123"

if "profile_img" not in st.session_state:
    st.session_state.profile_img = "https://i.imgur.com/8Km9tLL.png"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "history" not in st.session_state:
    st.session_state.history = []

if "last_watched" not in st.session_state:
    st.session_state.last_watched = "Henüz izlenmedi"

if "user_reviews" not in st.session_state:
    st.session_state.user_reviews = {}

if "favorite_anime" not in st.session_state:
    st.session_state.favorite_anime = "Henüz eklenmemiş"

if "community_posts" not in st.session_state:
    st.session_state.community_posts = [
        {"user": "AniSever01", "text": "Bugün Black Clover son arc'ını bitirdim, cidden harikaydı!", "likes": 5},
        {"user": "OtakuKing", "text": "Öneri motorundan bulduğum gizli bir hazine animeyi izliyorum, tavsiye ederim.", "likes": 3}
    ]


# =====================================================================
# 3. KAPSAMLI SÖZLÜKLER VE TÜRKÇE/İNGİLİZCE HARİTALAR
# =====================================================================
TUR_HARITASI = {
    "romantizm": "Romance", "romantik": "Romance", "romance": "Romance",
    "aksiyon": "Action", "action": "Action", "komedi": "Comedy", "comedy": "Comedy",
    "fantezi": "Fantasy", "fantastik": "Fantasy", "fantasy": "Fantasy",
    "dram": "Drama", "drama": "Drama", "macera": "Adventure", "adventure": "Adventure",
    "bilim kurgu": "Sci-Fi", "sci-fi": "Sci-Fi", "gerilim": "Thriller", "thriller": "Thriller",
    "korku": "Horror", "horror": "Horror", "spor": "Sports", "sports": "Sports",
    "isekai": "Fantasy", "büyü": "Fantasy", "magic": "Fantasy",
    "ecchi": "Ecchi", "hentai": "Hentai"
}

TURKCE_TUR_ISIMLERI = {
    "Action": "Aksiyon", "Adventure": "Macera", "Comedy": "Komedi", "Drama": "Dram",
    "Fantasy": "Fantastik / İsekai", "Horror": "Korku", "Mystery": "Gizem", "Romance": "Romantik",
    "Sci-Fi": "Bilim Kurgu", "Slice of Life": "Yaşamdan Kesitler", "Sports": "Spor",
    "Supernatural": "Doğaüstü", "Thriller": "Gerilim", "Ecchi": "Ecchi", "Hentai": "Hentai",
    "Music": "Müzik", "Mecha": "Mecha", "Psychological": "Psikolojik", "Mahou Shoujo": "Sihirli Kız"
}


# =====================================================================
# 4. YARDIMCI İŞLEVSEL FONKSİYONLAR
# =====================================================================
@st.cache_data(ttl=86400)
def turkceye_ceviri(metin):
    if not metin or not metin.strip():
        return "Açıklama bulunamadı."
    temiz_metin = re.sub(r"<[^>]+>", "", metin).strip()
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=tr&dt=t&q=" + urllib.parse.quote(temiz_metin)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            ceviri = "".join([parca[0] for parca in data[0] if parca[0]])
            return ceviri if ceviri else temiz_metin
    except Exception:
        return temiz_metin

def tur_isimlerini_turkcelestir(tur_listesi):
    if not tur_listesi:
        return "Bilinmiyor"
    return ", ".join([TURKCE_TUR_ISIMLERI.get(t, t) for t in tur_listesi])

def istegi_cozumle(metin):
    metin_kucuk = metin.lower()
    bulunanlar = []
    for anahtar, deger in TUR_HARITASI.items():
        if anahtar in metin_kucuk:
            bulunanlar.append(deger)
    return list(set(bulunanlar)) if bulunanlar else ["Action"]

def watchliste_ekle(anime_item):
    if not any(item['id'] == anime_item['id'] for item in st.session_state.watchlist):
        st.session_state.watchlist.append(anime_item)
        st.toast(f"✅ '{anime_item['title']}' izleme listene eklendi!")
    else:
        st.toast(f"⚠️ '{anime_item['title']}' zaten listende var!")

def gecmise_ekle(anime_adi):
    st.session_state.last_watched = anime_adi
    if anime_adi not in st.session_state.history:
        st.session_state.history.insert(0, anime_adi)

def animecix_url_olustur(arama_metni):
    return f"https://animecix.com/search?q={urllib.parse.quote(arama_metni)}"

def turkanime_url_olustur(arama_metni):
    return f"https://www.turkanime.co/?q={urllib.parse.quote(arama_metni)}"

def diziwatch_url_olustur(arama_metni):
    return f"https://diziwatch.net/?s={urllib.parse.quote(arama_metni)}"

def izleme_butonlarini_ciz(arama_metni):
    st.write(f"**🚀 İzleme Alternatifleri ({arama_metni}):**")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("▶️ Animecix", key=f"acix_{arama_metni}_{random.randint(1,100000)}", use_container_width=True):
            gecmise_ekle(arama_metni)
            st.link_button("Hemen Git (Animecix)", animecix_url_olustur(arama_metni), use_container_width=True)
    with b2:
        if st.button("▶️ Türkanime", key=f"turl_{arama_metni}_{random.randint(1,100000)}", use_container_width=True):
            gecmise_ekle(arama_metni)
            st.link_button("Hemen Git (Türkanime)", turkanime_url_olustur(arama_metni), use_container_width=True)
    with b3:
        if st.button("▶️ DiziWatch", key=f"dizi_{arama_metni}_{random.randint(1,100000)}", use_container_width=True):
            gecmise_ekle(arama_metni)
            st.link_button("Hemen Git (DiziWatch)", diziwatch_url_olustur(arama_metni), use_container_width=True)

def yorum_ve_puan_alani_ciz(anime_id, anime_adi):
    st.write("---")
    st.markdown("💬 **Kişisel Notlar, Puan ve Yorumlar**")
    mevcut_veri = st.session_state.user_reviews.get(anime_id, {"score": 5, "comment": ""})
    
    col_puan, _ = st.columns([1, 2])
    with col_puan:
        yeni_puan = st.slider(f"Puanın (1-10) - {anime_adi}", 1, 10, int(mevcut_veri["score"]), key=f"slider_{anime_id}")
    
    yeni_yorum = st.text_area(f"Yorumun / Notun ({anime_adi}):", value=mevcut_veri["comment"], key=f"comment_{anime_id}")
    
    if st.button("💾 Yorumu ve Puanı Kaydet", key=f"save_rev_{anime_id}"):
        st.session_state.user_reviews[anime_id] = {"score": yeni_puan, "comment": yeni_yorum}
        st.toast("✅ Değerlendirmen kaydedildi!")

def en_cok_izlenen_turu_bul():
    if not st.session_state.watchlist:
        return None
    tum_turler = []
    for item in st.session_state.watchlist:
        if "genres" in item and item["genres"]:
            tum_turler.extend(item["genres"])
    if not tum_turler:
        return None
    en_cok_tekrar_eden = Counter(tum_turler).most_common(1)
    return en_cok_tekrar_eden[0][0] if en_cok_tekrar_eden else None


# =====================================================================
# 5. ANA UYGULAMA SEKMELERİ (TÜM MODÜLLER)
# =====================================================================
st.title("🎬 AniZek — Eksiksiz Gelişmiş Anime Platformu")

tab_home, tab_search, tab_recom, tab_similar, tab_dice, tab_list, tab_player, tab_community, tab_profile = st.tabs([
    "🏠 Ana Sayfa",
    "🔍 Anime Ara",
    "🎯 Öneri Motoru",
    "🔗 Benzer Anime Bul",
    "🎲 Şans Zarı",
    "📌 İzleme Listem",
    "▶ Hızlı İzle",
    "💬 Topluluk",
    "👤 Profil"
])

# ---------------------------------------------------------------------
# TAB 0: ANA SAYFA
# ---------------------------------------------------------------------
with tab_home:
    en_sevilen_tur = en_cok_izlenen_turu_bul()
    if en_sevilen_tur:
        st.header(f"✨ Sizin İçin Önerilenler ({TURKCE_TUR_ISIMLERI.get(en_sevilen_tur, en_sevilen_tur)} Ağırlıklı)")

    col_v1, col_v2 = st.columns([4, 1])
    with col_v1:
        st.header("🔥 Trend ve Popüler Ana Akım Animeler")
    with col_v2:
        yenile_vitrin = st.button("🔄 Vitrini Yenile", key="btn_refresh_home")

    query_vitrin = """
    query ($page: Int) {
      Page (page: $page, perPage: 4) {
        media (type: ANIME, sort: POPULARITY_DESC, isAdult: false) {
          id title { english romaji } coverImage { extraLarge } episodes averageScore description genres
        }
      }
    }
    """
    sayfa_no = random.randint(1, 5) if yenile_vitrin else 1
    payload_v = json.dumps({"query": query_vitrin, "variables": {"page": sayfa_no}}).encode("utf-8")
    req_v = urllib.request.Request("https://graphql.anilist.co", data=payload_v, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req_v, timeout=8) as response:
            v_animeler = json.loads(response.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
            for anime in v_animeler:
                baslik = anime["title"]["english"] or anime["title"]["romaji"]
                ozet_tr = turkceye_ceviri(anime.get("description") or "")
                turler_tr = tur_isimlerini_turkcelestir(anime.get('genres', []))

                col_img, col_info = st.columns([1, 2.5])
                with col_img:
                    if anime.get("coverImage", {}).get("extraLarge"):
                        st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                    anime_obj = {
                        "id": anime["id"], "title": baslik,
                        "cover": anime.get("coverImage", {}).get("extraLarge"),
                        "score": anime.get('averageScore', 'N/A'),
                        "episodes": anime.get('episodes', 'Bilinmiyor'),
                        "genres": anime.get('genres', [])
                    }
                    st.button("➕ Listeme Ekle", key=f"add_home_{anime['id']}", on_click=watchliste_ekle, args=(anime_obj,), use_container_width=True)
                with col_info:
                    st.subheader(f"🎬 {baslik}")
                    st.write(f"⭐ **Puan:** {anime.get('averageScore', 'N/A')} / 100 | 📚 **Bölüm:** {anime.get('episodes', 'Bilinmiyor')}")
                    st.write(f"🏷 **Türler:** {turler_tr}")
                    st.markdown(f"**📖 Konusu:**\n{ozet_tr[:350]}...")
                    izleme_butonlarini_ciz(baslik)
                    yorum_ve_puan_alani_ciz(anime["id"], baslik)
                st.divider()
    except Exception:
        pass


# ---------------------------------------------------------------------
# TAB 1: ANİME ARAMA (5 KAYNAKLI DERİN TARAMA, TEMİZ MOD)
# ---------------------------------------------------------------------
with tab_search:
    st.header("🔍 Gelişmiş 5 Kaynaklı Genişletilmiş Anime Arama")
    anime_adi = st.text_input("Aramak istediğiniz anime:", placeholder="Örn: naruto, black clover, solo leveling...", key="search_input")
    
    if st.button("Anime Ara (Derin Tarama)", key="btn_tab1_search") and anime_adi:
        with st.spinner("5 farklı veri kaynağından ve yan yapımlardan taranıyor..."):
            temiz_arama = anime_adi.strip()
            toplam_bulunanlar = {}
            
            for sayfa in range(1, 6):
                query = """
                query ($search: String, $page: Int) {
                  Page (page: $page, perPage: 20) {
                    media (search: $search, type: ANIME, sort: [POPULARITY_DESC, SCORE_DESC], isAdult: false) {
                      id title { romaji english native } coverImage { extraLarge } episodes averageScore description genres format
                    }
                  }
                }
                """
                payload = json.dumps({"query": query, "variables": {"search": temiz_arama, "page": sayfa}}).encode("utf-8")
                req = urllib.request.Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = json.loads(response.read().decode("utf-8"))
                        liste = data.get("data", {}).get("Page", {}).get("media", [])
                        for anime in liste:
                            toplam_bulunanlar[anime["id"]] = anime
                except Exception:
                    continue
            
            anilist_sonuclari = list(toplam_bulunanlar.values())
            
            if anilist_sonuclari:
                st.success(f"🎯 Toplam **{len(anilist_sonuclari)}** sonuç (Ana seri, filmler, OVA'lar ve yan yapımlar) başarıyla listelendi:")
                for anime in anilist_sonuclari:
                    baslik = anime["title"]["english"] or anime["title"]["romaji"] or anime["title"]["native"]
                    ozet_tr = turkceye_ceviri(anime.get("description") or "")
                    turler_tr = tur_isimlerini_turkcelestir(anime.get('genres', []))
                    format_turu = anime.get('format', 'TV')
                    
                    col_i, col_f = st.columns([1, 3])
                    with col_i:
                        if anime.get("coverImage", {}).get("extraLarge"):
                            st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                        anime_obj = {
                            "id": anime["id"], "title": baslik,
                            "cover": anime.get("coverImage", {}).get("extraLarge"),
                            "score": anime.get('averageScore', 'N/A'),
                            "episodes": anime.get('episodes', 'Bilinmiyor'),
                            "genres": anime.get('genres', [])
                        }
                        st.button("➕ Listeye Ekle", key=f"add_search_{anime['id']}_{random.randint(1,100000)}", on_click=watchliste_ekle, args=(anime_obj,))
                    with col_f:
                        st.subheader(f"{baslik} ({format_turu})")
                        st.write(f"⭐ Puan: {anime.get('averageScore', 'N/A')} | 📚 Bölüm: {anime.get('episodes', 'Bilinmiyor')} | 📌 Format: {format_turu}")
                        st.write(f"🏷️ Türler: {turler_tr}")
                        st.write(f"{ozet_tr[:300]}...")
                        izleme_butonlarini_ciz(baslik)
                    st.divider()
            else:
                st.warning("Aradığınız kritere uygun hiçbir yapıma ulaşılamadı. Lütfen farklı bir anahtar kelime deneyin.")


# ---------------------------------------------------------------------
# TAB 2: ÖNERİ MOTORU (GÜVENLİ MOD)
# ---------------------------------------------------------------------
with tab_recom:
    st.header("🎯 Kriterli Öneri Motoru (Güvenli Mod)")
    
    col_r1, col_r2 = st.columns([3, 1])
    with col_r1:
        kriter_input = st.text_input("İstediğiniz türler / özellikler (Örn: Aksiyon, isekai, romantizm, fantastik):", key="recom_input")
    with col_r2:
        bolum_filtresi = st.selectbox("Bölüm Aralığı Filtresi", ["Tümü", "Kısa (< 13 Bölüm)", "Orta (13 - 26 Bölüm)", "Uzun (> 26 Bölüm)"])

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        oneriyi_getir = st.button("🎯 Öneri Getir", key="btn_recom_get")
    with col_btn2:
        yenile_oneriyi = st.button("🔄 Başka Öneriler Getir", key="btn_recom_refresh")

    if oneriyi_getir or yenile_oneriyi:
        if kriter_input.strip():
            bulunan_turler = istegi_cozumle(kriter_input)
            secilen_genre = bulunan_turler[0] if bulunan_turler else "Action"
            
            istiyor_mu_hentai = "hentai" in kriter_input.lower()
            guvenli_is_adult = True if istiyor_mu_hentai else False
            
            rastgele_sayfa = random.randint(1, 10)
            
            query_rec = """
            query ($genre: String, $page: Int, $isAdult: Boolean) {
              Page (page: $page, perPage: 20) {
                media (genre: $genre, type: ANIME, sort: SCORE_DESC, isAdult: $isAdult) {
                  id title { english romaji } coverImage { extraLarge } episodes averageScore description genres
                }
              }
            }
            """
            payload_rec = json.dumps({
                "query": query_rec, 
                "variables": {"genre": secilen_genre, "page": rastgele_sayfa, "isAdult": guvenli_is_adult}
            }).encode("utf-8")
            
            req_rec = urllib.request.Request("https://graphql.anilist.co", data=payload_rec, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req_rec, timeout=8) as resp_rec:
                    animeler_rec = json.loads(resp_rec.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
                    
                    filtrelenmis_animeler = []
                    for anime in animeler_rec:
                        eps = anime.get("episodes")
                        if bolum_filtresi == "Kısa (< 13 Bölüm)" and (eps is None or eps >= 13): continue
                        if bolum_filtresi == "Orta (13 - 26 Bölüm)" and (eps is None or not (13 <= eps <= 26)): continue
                        if bolum_filtresi == "Uzun (> 26 Bölüm)" and (eps is None or eps <= 26): continue
                        filtrelenmis_animeler.append(anime)
                    
                    gosterilecek_liste = filtrelenmis_animeler[:3] if filtrelenmis_animeler else animeler_rec[:3]
                    
                    if not gosterilecek_liste:
                        st.warning("Bu kriterlere uygun anime bulunamadı.")
                    
                    for anime in gosterilecek_liste:
                        baslik = anime["title"]["english"] or anime["title"]["romaji"]
                        ozet_tr = turkceye_ceviri(anime.get("description") or "")
                        turler_tr = tur_isimlerini_turkcelestir(anime.get('genres', []))
                        
                        col_img, col_detay = st.columns([1, 3])
                        with col_img:
                            if anime.get("coverImage", {}).get("extraLarge"):
                                st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                            anime_obj = {
                                "id": anime["id"], "title": baslik,
                                "cover": anime.get("coverImage", {}).get("extraLarge"),
                                "score": anime.get('averageScore', 'N/A'),
                                "episodes": anime.get('episodes', 'Bilinmiyor'),
                                "genres": anime.get('genres', [])
                            }
                            st.button("➕ Listeye Ekle", key=f"add_recom_{anime['id']}_{random.randint(1,100000)}", on_click=watchliste_ekle, args=(anime_obj,))
                        with col_detay:
                            st.subheader(baslik)
                            st.write(f"⭐ Puan: {anime.get('averageScore', 'N/A')} | 📚 Bölüm: {anime.get('episodes', 'Bilinmiyor')}")
                            st.write(f"🏷️ Türler: {turler_tr}")
                            st.write(f"{ozet_tr[:300]}...")
                            izleme_butonlarini_ciz(baslik)
                        st.divider()
            except Exception as e:
                st.error(f"Öneri alınırken hata oluştu: {e}")


# ---------------------------------------------------------------------
# TAB 3: BENZER ANİME BUL
# ---------------------------------------------------------------------
with tab_similar:
    st.header("🔗 Benzer Anime Bulucu")
    st.write("Sevdiğin bir animeyi yaz, onunla benzer türlere ve temaya sahip yapımları keşfet!")
    
    benzer_arama = st.text_input("Örnek Alınacak Anime Adı:", placeholder="Örn: Naruto, Solo Leveling, Bleach...", key="similar_input")

    if st.button("🔍 Benzerlerini Bul", key="btn_find_similar") and benzer_arama:
        with st.spinner("Benzer animeler aranıyor..."):
            q_find = """
            query ($search: String) {
              Media (search: $search, type: ANIME, isAdult: false) {
                id title { english romaji } genres
              }
            }
            """
            p_find = json.dumps({"query": q_find, "variables": {"search": benzer_arama}}).encode("utf-8")
            r_find = urllib.request.Request("https://graphql.anilist.co", data=p_find, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            
            try:
                with urllib.request.urlopen(r_find, timeout=8) as resp_f:
                    f_data = json.loads(resp_f.read().decode("utf-8")).get("data", {}).get("Media")
                    if f_data and f_data.get("genres"):
                        ana_turler = f_data["genres"]
                        ana_baslik = f_data["title"]["english"] or f_data["title"]["romaji"]
                        st.info(f"📌 **{ana_baslik}** adlı yapımın türleri baz alınarak benzerler listeleniyor: {', '.join(ana_turler)}")
                        
                        hedef_tur = ana_turler[0]
                        q_sim = """
                        query ($genre: String) {
                          Page (page: 1, perPage: 4) {
                            media (genre: $genre, type: ANIME, sort: SCORE_DESC, isAdult: false) {
                              id title { english romaji } coverImage { extraLarge } episodes averageScore description genres
                            }
                          }
                        }
                        """
                        p_sim = json.dumps({"query": q_sim, "variables": {"genre": hedef_tur}}).encode("utf-8")
                        r_sim = urllib.request.Request("https://graphql.anilist.co", data=p_sim, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                        
                        with urllib.request.urlopen(r_sim, timeout=8) as resp_s:
                            sim_animeler = json.loads(resp_s.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
                            for anime in sim_animeler:
                                if anime["id"] == f_data["id"]: continue
                                b_baslik = anime["title"]["english"] or anime["title"]["romaji"]
                                b_ozet = turkceye_ceviri(anime.get("description") or "")
                                b_turler = tur_isimlerini_turkcelestir(anime.get('genres', []))
                                
                                c_img, c_det = st.columns([1, 3])
                                with c_img:
                                    if anime.get("coverImage", {}).get("extraLarge"):
                                        st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                                    a_obj = {
                                        "id": anime["id"], "title": b_baslik,
                                        "cover": anime.get("coverImage", {}).get("extraLarge"),
                                        "score": anime.get('averageScore', 'N/A'),
                                        "episodes": anime.get('episodes', 'Bilinmiyor'),
                                        "genres": anime.get('genres', [])
                                    }
                                    st.button("➕ Listeye Ekle", key=f"add_sim_{anime['id']}_{random.randint(1,100000)}", on_click=watchliste_ekle, args=(a_obj,))
                                with c_det:
                                    st.subheader(b_baslik)
                                    st.write(f"⭐ Puan: {anime.get('averageScore', 'N/A')} | 📚 Bölüm: {anime.get('episodes', 'Bilinmiyor')}")
                                    st.write(f"🏷 Türler: {b_turler}")
                                    st.write(f"{b_ozet[:300]}...")
                                    izleme_butonlarini_ciz(b_baslik)
                                st.divider()
                    else:
                        st.warning("Aradığınız anime bulunamadı.")
            except Exception as e:
                st.error(f"Hata oluştu: {e}")


# ---------------------------------------------------------------------
# TAB 4: ŞANS ZARI (HENTAI DESTEKLİ DENGELİ MOD)
# ---------------------------------------------------------------------
with tab_dice:
    st.header("🎲 Rastgele Sürpriz Anime")
    st.write("Ne izleyeceğine karar veremiyorsan zarını at ve sürpriz bir yapım keşfet!")
    
    zar_modu = st.radio("Zar Modu Seçin:", ["Tüm Türler (Genel Popüler ve Kaliteli)", "Belirli Bir Tür Seçerek Zar At"], horizontal=True)
    
    secilen_zar_turu = "Action"
    secilen_tur_tr = "Aksiyon"
    if zar_modu == "Belirli Bir Tür Seçerek Zar At":
        secilen_tur_tr = st.selectbox("Tür Seçin:", list(TURKCE_TUR_ISIMLERI.values()), key="dice_genre_select")
        for eng, tr in TURKCE_TUR_ISIMLERI.items():
            if tr == secilen_tur_tr:
                secilen_zar_turu = eng
                break

    if st.button("🎲 Zar At & Sürpriz Seç", key="btn_dice_roll"):
        with st.spinner("Şans zarı atılıyor..."):
            rnd_page = random.randint(1, 15)
            
            # Eğer seçilen tür Hentai ise isAdult parametresi otomatik true yapılır, aksi takdirde false kalır
            is_hentai_mode = (secilen_zar_turu == "Hentai")
            
            if zar_modu == "Tüm Türler (Genel Popüler ve Kaliteli)":
                query_dice = """
                query ($page: Int) {
                  Page (page: $page, perPage: 1) {
                    media (type: ANIME, sort: SCORE_DESC, isAdult: false) {
                      id title { english romaji } coverImage { extraLarge } episodes averageScore description genres
                    }
                  }
                }
                """
                variables = {"page": rnd_page}
            else:
                query_dice = """
                query ($page: Int, $genre: String, $isAdult: Boolean) {
                  Page (page: $page, perPage: 1) {
                    media (genre: $genre, type: ANIME, sort: SCORE_DESC, isAdult: $isAdult) {
                      id title { english romaji } coverImage { extraLarge } episodes averageScore description genres
                    }
                  }
                }
                """
                variables = {"page": rnd_page, "genre": secilen_zar_turu, "isAdult": is_hentai_mode}

            payload_dice = json.dumps({"query": query_dice, "variables": variables}).encode("utf-8")
            req_dice = urllib.request.Request("https://graphql.anilist.co", data=payload_dice, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req_dice, timeout=8) as resp_dice:
                    dice_data = json.loads(resp_dice.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
                    if dice_data:
                        anime = dice_data[0]
                        baslik = anime["title"]["english"] or anime["title"]["romaji"]
                        ozet_tr = turkceye_ceviri(anime.get("description") or "")
                        turler_tr = tur_isimlerini_turkcelestir(anime.get('genres', []))

                        st.success(f"🎉 Şansına Çıkan Sürpriz Anime: **{baslik}**")
                        c_img, c_inf = st.columns([1, 2.5])
                        with c_img:
                            if anime.get("coverImage", {}).get("extraLarge"):
                                st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                        with c_inf:
                            st.write(f"⭐ **Puan:** {anime.get('averageScore', 'N/A')} / 100 | 📚 **Bölüm:** {anime.get('episodes', 'Bilinmiyor')}")
                            st.write(f"🏷 **Türler:** {turler_tr}")
                            st.markdown(f"**📖 Konusu:**\n{ozet_tr[:350]}...")
                            izleme_butonlarini_ciz(baslik)
            except Exception as e:
                st.error(f"Hata oluştu: {e}")


# ---------------------------------------------------------------------
# TAB 5: İZLEME LİSTEM
# ---------------------------------------------------------------------
with tab_list:
    st.header("📌 Kaydedilen İzleme Listem")
    if not st.session_state.watchlist:
        st.info("İzleme listeniz şu an boş.")
    else:
        for index, item in enumerate(st.session_state.watchlist):
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if item.get("cover"): st.image(item["cover"], use_container_width=True)
            with col2:
                st.subheader(item["title"])
                st.write(f"⭐ Puan: {item.get('score')} | 📚 Bölüm: {item.get('episodes')}")
                izleme_butonlarini_ciz(item['title'])
                yorum_ve_puan_alani_ciz(item['id'], item['title'])
            with col3:
                if st.button("❌ Listeden Kaldır", key=f"del_{item['id']}_{index}"):
                    st.session_state.watchlist.pop(index)
                    st.rerun()
            st.divider()


# ---------------------------------------------------------------------
# TAB 6: HIZLI YÖNLENDİRİCİ
# ---------------------------------------------------------------------
with tab_player:
    st.header("▶ Doğrudan Platform Yönlendiricisi")
    hedef_anime_adi = st.text_input("İzlemek istediğin animeyi yaz:", key="direct_player_input")
    if hedef_anime_adi:
        izleme_butonlarini_ciz(hedef_anime_adi)


# ---------------------------------------------------------------------
# TAB 7: TOPLULUK & POSTLAR
# ---------------------------------------------------------------------
with tab_community:
    st.header("💬 Topluluk & Post Akışı")
    st.write("Diğer kullanıcılarla düşüncelerini paylaş, post gönder!")
    
    with st.form("post_form"):
        yeni_mesaj = st.text_area("Ne düşünüyorsun?", placeholder="Favori sahnelerinden veya önerilerinden bahset...")
        gonder_tusu = st.form_submit_button("🚀 Gönderiyi Paylaş")
        if gonder_tusu and yeni_mesaj.strip():
            st.session_state.community_posts.insert(0, {
                "user": st.session_state.username,
                "text": yeni_mesaj,
                "likes": 0
            })
            st.success("Postun başarıyla paylaşıldı!")
            
    st.markdown("---")
    st.subheader("📜 Akıştakiler")
    for i, post in enumerate(st.session_state.community_posts):
        st.markdown(f"""
        <div class="post-box">
            <b>@{post['user']}</b><br>
            {post['text']}<br>
            <small>❤️ {post['likes']} Beğeni</small>
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# TAB 8: HESAP & PROFİL
# ---------------------------------------------------------------------
with tab_profile:
    st.markdown("## 👤 Hesap & Profil Yönetimi")
    
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        st.markdown("### 🖼 Profil Fotoğrafı")
        st.image(st.session_state.profile_img, width=120)
    with col_p2:
        st.markdown(f"### Hoş Geldin, **{st.session_state.username}**! ✨")
        yeni_kullanici_adi = st.text_input("Kullanıcı Adını Güncelle:", value=st.session_state.username)
        if st.button("💾 Kullanıcı Adını Kaydet"):
            st.session_state.username = yeni_kullanici_adi
            st.success("Kullanıcı adı güncellendi!")

    st.write("---")
    st.markdown("### 📁 Galeriden Profil Fotoğrafı Seç / Yükle")
    yuklenen_dosya = st.file_uploader("Cihazınızdan bir görsel seçin (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])
    if yuklenen_dosya is not None:
        st.session_state.profile_img = yuklenen_dosya
        st.success("✅ Profil fotoğrafı galeriden başarıyla güncellendi!")
        st.rerun()

    st.write("---")
    st.markdown("### 📊 İstatistikler ve Geçmiş")
    
    secilen_favori = st.text_input("En sevdiğin animeyi yaz:", value=st.session_state.favorite_anime, key="fav_anime_input")
    if st.button("💾 Favori Animi Kaydet"):
        st.session_state.favorite_anime = secilen_favori
        st.success(f"Favori anime '{secilen_favori}' olarak kaydedildi!")

    st.write("")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(label="İzleme Listesindeki Yapımlar", value=f"{len(st.session_state.watchlist)} Yapım")
    with c2:
        st.metric(label="Favori Anime", value=st.session_state.favorite_anime)
    with c3:
        st.metric(label="Son İzlenen", value=str(st.session_state.last_watched))
