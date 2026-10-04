import json
import random
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

# Sayfa Yapılandırması
st.set_page_config(page_title="Anime Rehberi & Öneri", page_icon="🎬", layout="wide")

# Tür ve Etiket Sözlükleri
TUR_HARITASI = {
    "romantizm": "Romance", "romantik": "Romance", "romance": "Romance",
    "aksiyon": "Action", "action": "Action", "komedi": "Comedy", "comedy": "Comedy",
    "fantezi": "Fantasy", "fantastik": "Fantasy", "fantasy": "Fantasy",
    "dram": "Drama", "drama": "Drama", "macera": "Adventure", "adventure": "Adventure",
    "bilim kurgu": "Sci-Fi", "sci-fi": "Sci-Fi", "gerilim": "Thriller", "thriller": "Thriller",
    "korku": "Horror", "horror": "Horror", "spor": "Sports", "sports": "Sports",
    "ecchi": "Ecchi", "hentai": "Hentai"
}

ETIKET_HARITASI = {
    "shounen": "Shounen", "shonen": "Shounen", "lise": "School", "okul": "School",
    "school": "School", "isekai": "Isekai", "seinen": "Seinen", "shoujo": "Shoujo",
    "sihir": "Magic", "büyü": "Magic", "magic": "Magic", "süper güç": "Super Power",
    "super power": "Super Power",
}


@st.cache_data(ttl=3600)
def turkceye_ceviri(metin):
    if not metin:
        return metin
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q=" + urllib.parse.quote(metin)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return "".join([parca[0] for parca in data[0] if parca[0]])
    except Exception:
        return metin


def istegi_cozumle(metin):
    metin_kucuk = metin.lower()
    tespit_edilen_turler = [deger for anahtar, deger in TUR_HARITASI.items() if anahtar in metin_kucuk]
    tespit_edilen_etiketler = [deger for anahtar, deger in ETIKET_HARITASI.items() if anahtar in metin_kucuk]
    return list(set(tespit_edilen_turler)), list(set(tespit_edilen_etiketler))


def fetch_jikan(anime_adi, bolum_no):
    try:
        search_url = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(anime_adi)}&limit=1"
        req_search = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_search, timeout=8) as response:
            results = json.loads(response.read().decode("utf-8")).get("data", [])
            if not results:
                return None
            mal_id = results[0]["mal_id"]

            ep_url = f"https://api.jikan.moe/v4/anime/{mal_id}/episodes/{bolum_no}"
            req_ep = urllib.request.Request(ep_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_ep, timeout=8) as ep_response:
                ep_data = json.loads(ep_response.read().decode("utf-8")).get("data", {})
                
                aired = ep_data.get("aired")
                tarih = aired.split("T")[0] if aired else None

                return {
                    "score": ep_data.get("score"),
                    "filler": ep_data.get("filler", False),
                    "synopsis": ep_data.get("synopsis"),
                    "title": ep_data.get("title"),
                    "airdate": tarih
                }
    except Exception:
        return None


def fetch_kitsu(anime_adi, bolum_no):
    try:
        search_url = f"https://kitsu.io/api/edge/anime?filter[text]={urllib.parse.quote(anime_adi)}"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            anime_list = data.get("data", [])
            if not anime_list:
                return None
            kitsu_id = anime_list[0]["id"]

            ep_url = f"https://kitsu.io/api/edge/anime/{kitsu_id}/episodes?filter[number]={bolum_no}"
            req_ep = urllib.request.Request(ep_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_ep, timeout=6) as ep_response:
                ep_data = json.loads(ep_response.read().decode("utf-8"))
                ep_list = ep_data.get("data", [])
                if ep_list:
                    attr = ep_list[0]["attributes"]
                    return {
                        "title": attr.get("canonicalTitle"),
                        "airdate": attr.get("airdate"),
                        "synopsis": attr.get("synopsis")
                    }
    except Exception:
        return None


# --- ARAYÜZ (STREAMLIT) ---
st.title("🎬 Akıllı Anime Bulucu & Öneri Rehberi")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Anime Arama & Bölüm Detayı",
    "🎯 Kriterli Öneri Motoru",
    "✨ Benzer Yapımları Bul",
    "🎲 Şans Zarı"
])

# --- TAB 1: ANİME ARAMA ---
with tab1:
    st.header("Anime Genel Bilgi & Bölüm Tarama")
    anime_adi = st.text_input("Anime Adı Girin:", placeholder="Örn: Black Clover, Naruto...")
    arama_tipi = st.radio("İşlem Türü:", ["Genel Anime Bilgisi", "Özel Bölüm Detayı Taraması"])

    bolum_no = 1
    if arama_tipi == "Özel Bölüm Detayı Taraması":
        bolum_no = st.number_input("Kaçıncı Bölüm?", min_value=1, value=1, step=1)

    if st.button("Bilgileri Getir", key="btn_tab1"):
        if not anime_adi:
            st.warning("Lütfen bir anime adı yazın!")
        else:
            with st.spinner("Veriler çekiliyor..."):
                if arama_tipi == "Genel Anime Bilgisi":
                    query = """
                    query ($search: String) {
                      Page (page: 1, perPage: 5) {
                        media (search: $search, type: ANIME, sort: SEARCH_MATCH) {
                          id
                          title { romaji english }
                          coverImage { extraLarge }
                          status
                          startDate { year month day }
                          episodes
                          averageScore
                          genres
                          description
                          nextAiringEpisode { timeUntilAiring episode }
                        }
                      }
                    }
                    """
                    payload = json.dumps({"query": query, "variables": {"search": anime_adi}}).encode("utf-8")
                    req = urllib.request.Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

                    try:
                        with urllib.request.urlopen(req, timeout=6) as response:
                            res_data = json.loads(response.read().decode("utf-8"))
                            liste = res_data.get("data", {}).get("Page", {}).get("media", [])

                            if not liste:
                                st.error("Anime bulunamadı!")
                            else:
                                anime = liste[0]
                                baslik = anime["title"]["english"] or anime["title"]["romaji"]
                                ozet = re.sub(r"<[^>]+>", "", anime.get("description") or "Konu yok.")
                                turkce_ozet = turkceye_ceviri(ozet)

                                col1, col2 = st.columns([1, 2])
                                with col1:
                                    if anime.get("coverImage", {}).get("extraLarge"):
                                        st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                                with col2:
                                    st.subheader(baslik)
                                    st.write(f"**⭐ Genel Puan:** {anime.get('averageScore', 'N/A')} / 100")
                                    st.write(f"**📚 Toplam Bölüm:** {anime.get('episodes', 'Bilinmiyor')}")
                                    st.write(f"**🏷️️ Türler:** {', '.join(anime.get('genres', []))}")
                                    
                                    durum = anime.get("status")
                                    if durum == "FINISHED":
                                        st.success("🔴 Yayın Durumu: Tamamlandı (Bitti)")
                                    elif durum == "RELEASING":
                                        st.info("🟢 Yayın Durumu: Devam Ediyor")
                                        if anime.get("nextAiringEpisode"):
                                            nxt = anime["nextAiringEpisode"]
                                            gun = nxt["timeUntilAiring"] // 86400
                                            st.write(f"⏰ **Gelecek Bölüm:** {nxt['episode']}. Bölüm ({gun} gün kaldı)")

                                    st.markdown(f"**📖 Konusu:**\n{turkce_ozet}")
                    except Exception as e:
                        st.error(f"Hata oluştu: {e}")

                else:
                    # Bölüm Detay Tarama
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        f_jikan = executor.submit(fetch_jikan, anime_adi, bolum_no)
                        f_kitsu = executor.submit(fetch_kitsu, anime_adi, bolum_no)
                        jikan_veri = f_jikan.result()
                        kitsu_veri = f_kitsu.result()

                    ep_title = None
                    puan_str = "Bilinmiyor"
                    filler_str = "🟢 Hayır (Kanon / Ana Hikaye)"
                    synopsis = None
                    airdate = "Bilinmiyor"

                    if jikan_veri:
                        if jikan_veri.get("score"):
                            puan_str = f"{jikan_veri['score']} / 10"
                        if jikan_veri.get("filler"):
                            filler_str = "⚠ Evet (Filler / Doldurma)"
                        ep_title = jikan_veri.get("title")
                        synopsis = jikan_veri.get("synopsis")
                        if jikan_veri.get("airdate"):
                            airdate = jikan_veri["airdate"]

                    if kitsu_veri:
                        if not ep_title:
                            ep_title = kitsu_veri.get("title")
                        if not synopsis:
                            synopsis = kitsu_veri.get("synopsis")
                        if airdate == "Bilinmiyor" and kitsu_veri.get("airdate"):
                            airdate = kitsu_veri["airdate"]

                    if not ep_title:
                        ep_title = f"{bolum_no}. Bölüm"

                    st.subheader(f"🎬 {anime_adi.title()} - {bolum_no}. Bölüm")
                    st.write(f"**📌 Bölüm Adı:** {turkceye_ceviri(ep_title)}")
                    st.write(f"**📅 Yayın Tarihi:** {airdate}")
                    st.write(f"**⭐ Bölüm Puanı:** {puan_str}")
                    st.write(f"**🧩 Filler Mı?:** {filler_str}")
                    
                    if synopsis:
                        st.markdown(f"**📖 Bölüm Özeti:**\n{turkceye_ceviri(synopsis)}")
                    else:
                        st.info("Bu bölüm için henüz özet verisi bulunamadı.")


# --- TAB 2: KRİTERLİ ÖNERİ MOTORU ---
with tab2:
    st.header("Özellik ve Bölüm Sayısına Göre Öneri")
    kriter = st.text_input("İstediğiniz Özellikler/Türler:", placeholder="Örn: shounen aksiyon, lise komedi...")
    bolum_secimi = st.selectbox("Bölüm Sayısı Tercihi:", [
        "Fark Etmez / Tümü",
        "Kısa / Çerezlik (1 - 13 Bölüm)",
        "Orta Sezonluk (13 - 30 Bölüm)",
        "Uzun Soluklu (30+ Bölüm)"
    ])

    if st.button("Öneri Getir", key="btn_tab2"):
        with st.spinner("Öneriler hazırlanıyor..."):
            turler, etiketler = istegi_cozumle(kriter)
            query = """
            query ($genre_in: [String], $tag_in: [String], $genre_not_in: [String], $isAdult: Boolean, $episodes_greater: Int, $episodes_lesser: Int) {
              Page (page: 1, perPage: 6) {
                media (genre_in: $genre_in, tag_in: $tag_in, genre_not_in: $genre_not_in, episodes_greater: $episodes_greater, episodes_lesser: $episodes_lesser, type: ANIME, isAdult: $isAdult, sort: SCORE_DESC) {
                  title { english romaji }
                  coverImage { extraLarge }
                  startDate { year }
                  episodes
                  averageScore
                  description
                  genres
                }
              }
            }
            """
            variables = {}
            if "Kısa" in bolum_secimi:
                variables["episodes_greater"] = 0
                variables["episodes_lesser"] = 14
            elif "Orta" in bolum_secimi:
                variables["episodes_greater"] = 13
                variables["episodes_lesser"] = 31
            elif "Uzun" in bolum_secimi:
                variables["episodes_greater"] = 30

            if "Ecchi" not in turler and "Hentai" not in turler:
                variables["genre_not_in"] = ["Ecchi", "Hentai"]
                variables["isAdult"] = False

            if turler: variables["genre_in"] = turler
            if etiketler: variables["tag_in"] = etiketler

            payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
            req = urllib.request.Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

            try:
                with urllib.request.urlopen(req, timeout=6) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    animeler = res_data.get("data", {}).get("Page", {}).get("media", [])

                    if not animeler:
                        st.warning("Bu kriterlere uygun anime bulunamadı.")
                    else:
                        for anime in animeler:
                            baslik = anime["title"]["english"] or anime["title"]["romaji"]
                            ozet = re.sub(r"<[^>]+>", "", anime.get("description") or "")[:200] + "..."
                            
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                if anime.get("coverImage", {}).get("extraLarge"):
                                    st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                            with col2:
                                st.subheader(baslik)
                                st.write(f"⭐ **Puan:** {anime.get('averageScore', 'N/A')} | 📚 **Bölüm:** {anime.get('episodes', 'Bilinmiyor')} | 📅 **Yıl:** {anime.get('startDate', {}).get('year', 'N/A')}")
                                st.write(f"🏷️ **Türler:** {', '.join(anime.get('genres', []))}")
                                st.write(f"📖 {turkceye_ceviri(ozet)}")
                            st.divider()
            except Exception as e:
                st.error(f"Hata: {e}")


# --- TAB 3: BENZER YAPIMLARI BUL ---
with tab3:
    st.header("Sevdiğin Bir Animeye Benzer Yapımları Bul")
    hedef_anime = st.text_input("Sevdiğiniz Animenin Adı:", placeholder="Örn: Death Note, Hunter x Hunter...")

    if st.button("Benzerlerini Bul", key="btn_tab3"):
        if hedef_anime:
            with st.spinner("Analiz ediliyor..."):
                query_search = """
                query ($search: String) {
                  Media (search: $search, type: ANIME) {
                    id
                    title { english romaji }
                    genres
                  }
                }
                """
                payload_search = json.dumps({"query": query_search, "variables": {"search": hedef_anime}}).encode("utf-8")
                req_search = urllib.request.Request("https://graphql.anilist.co", data=payload_search, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

                try:
                    with urllib.request.urlopen(req_search, timeout=6) as response:
                        res_search = json.loads(response.read().decode("utf-8"))
                        target = res_search.get("data", {}).get("Media")

                        if target:
                            query_similar = """
                            query ($genre_in: [String], $genre_not_in: [String]) {
                              Page (page: 1, perPage: 8) {
                                media (genre_in: $genre_in, genre_not_in: $genre_not_in, type: ANIME, isAdult: false, sort: SCORE_DESC) {
                                  id
                                  title { english romaji }
                                  coverImage { extraLarge }
                                  episodes
                                  averageScore
                                  description
                                  genres
                                }
                              }
                            }
                            """
                            vars_sim = {"genre_in": target["genres"], "genre_not_in": ["Ecchi", "Hentai"]}
                            payload_sim = json.dumps({"query": query_similar, "variables": vars_sim}).encode("utf-8")
                            req_sim = urllib.request.Request("https://graphql.anilist.co", data=payload_sim, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

                            with urllib.request.urlopen(req_sim, timeout=6) as res_sim_resp:
                                animeler = json.loads(res_sim_resp.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
                                benzerler = [a for a in animeler if a["id"] != target["id"]][:4]

                                for anime in benzerler:
                                    baslik = anime["title"]["english"] or anime["title"]["romaji"]
                                    ozet = re.sub(r"<[^>]+>", "", anime.get("description") or "")[:200] + "..."
                                    col1, col2 = st.columns([1, 4])
                                    with col1:
                                        if anime.get("coverImage", {}).get("extraLarge"):
                                            st.image(anime["coverImage"]["extraLarge"], use_container_width=True)
                                    with col2:
                                        st.subheader(baslik)
                                        st.write(f"⭐ **Puan:** {anime.get('averageScore', 'N/A')} | 📚 **Bölüm:** {anime.get('episodes', 'Bilinmiyor')}")
                                        st.write(f"🏷️ **Türler:** {', '.join(anime.get('genres', []))}")
                                        st.write(f"📖 {turkceye_ceviri(ozet)}")
                                    st.divider()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")


# --- TAB 4: ŞANS ZARI ---
with tab4:
    st.header("🎲 Rastgele Sürpriz Anime")
    zar_tur = st.text_input("Özel bir türde zar atmak ister misin? (Boş bırakırsan tüm türler kapsanır):", placeholder="Örn: komedi, isekai...")

    if st.button("🎲 Zarı At!", key="btn_tab4"):
        with st.spinner("Zar dönüyor..."):
            query = """
            query ($genre_in: [String], $genre_not_in: [String], $isAdult: Boolean) {
              Page (page: 1, perPage: 40) {
                media (genre_in: $genre_in, genre_not_in: $genre_not_in, type: ANIME, isAdult: $isAdult, sort: POPULARITY_DESC) {
                  title { english romaji }
                  coverImage { extraLarge }
                  episodes
                  averageScore
                  description
                  genres
                }
              }
            }
            """
            variables = {"genre_not_in": ["Ecchi", "Hentai"], "isAdult": False}
            if zar_tur:
                turler, _ = istegi_cozumle(zar_tur)
                if turler: variables["genre_in"] = turler

            payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
            req = urllib.request.Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})

            try:
                with urllib.request.urlopen(req, timeout=6) as response:
                    animeler = json.loads(response.read().decode("utf-8")).get("data", {}).get("Page", {}).get("media", [])
                    if animeler:
                        secilen = random.choice(animeler)
                        baslik = secilen["title"]["english"] or secilen["title"]["romaji"]
                        ozet = re.sub(r"<[^>]+>", "", secilen.get("description") or "")
                        
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if secilen.get("coverImage", {}).get("extraLarge"):
                                st.image(secilen["coverImage"]["extraLarge"], use_container_width=True)
                        with col2:
                            st.subheader(f"🎯 Sürpriz Yapım: {baslik}")
                            st.write(f"⭐ **Puan:** {secilen.get('averageScore', 'N/A')} / 100 | 📚 **Bölüm:** {secilen.get('episodes', 'Bilinmiyor')}")
                            st.write(f"🏷️ **Türler:** {', '.join(secilen.get('genres', []))}")
                            st.markdown(f"**📖 Konusu:**\n{turkceye_ceviri(ozet)}")
            except Exception as e:
                st.error(f"Hata: {e}")
                