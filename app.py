import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

# --- CONFIGURATION ---
st.set_page_config(page_title="D&D Manager V19", page_icon="🐉", layout="wide")

# --- CONNEXION HYBRIDE ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_connection():
    try:
        local_key = Path("service_account.json")
        if local_key.is_file():
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        elif "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            return None
        client = gspread.authorize(creds)
        sheet = client.open("DndData").sheet1
        return sheet
    except: return None

sheet = init_connection()

# --- CONSTANTES ---
CLASSES_DATA = {
    "Barbare": "d12", "Barde": "d8", "Clerc": "d8", "Druide": "d8",
    "Ensorceleur": "d6", "Guerrier": "d10", "Magicien": "d6",
    "Moine": "d8", "Paladin": "d10", "Rôdeur": "d10",
    "Roublard": "d8", "Sorcier": "d8", "Artificier": "d8"
}
LISTE_CLASSES = sorted(list(CLASSES_DATA.keys()))

# --- FONCTIONS BACKEND ---
def charger_donnees():
    if sheet is None: return {}
    try:
        records = sheet.get_all_values()
        db = {}
        for row in records[1:]:
            if len(row) >= 2:
                try: db[row[0]] = json.loads(row[1])
                except: pass
        return db
    except: return {}

def sauvegarder_donnees(data):
    if sheet is None: return
    try:
        rows = [["NOM_PERSO", "DATA_JSON"]]
        for nom, p_data in data.items():
            rows.append([nom, json.dumps(p_data, ensure_ascii=False)])
        sheet.clear()
        sheet.update(rows)
    except Exception as e:
        st.error(f"Erreur Cloud: {e}")

def nouveau_perso_template():
    return {
        "infos": {"nom": "Nouveau Héros", "race": "Humain", "classe": "Guerrier", "niveau": 1},
        "hp": {"max": 10, "actuel": 10, "temp": 0},
        "hit_dice_used": 0,
        "features": [],
        "items": [],
        "spells_active": False,
        "spells": {str(i): {"max": 0, "actuel": 0} for i in range(1, 10)} 
    }

def calculer_bm(niveau):
    return 2 + (niveau - 1) // 4

def make_dirty():
    st.session_state.unsaved_changes = True

# --- CALLBACKS (SYNC WIDGETS) ---

def cb_manual_input(keys_path, widget_key):
    """Met à jour la donnée quand le widget change"""
    val = st.session_state[widget_key]
    ref = st.session_state.perso
    for key in keys_path[:-1]: ref = ref[key]
    ref[keys_path[-1]] = val
    make_dirty()

def cb_update_spell(lvl, change):
    perso = st.session_state.perso
    current = perso["spells"][lvl]["actuel"]
    maximum = perso["spells"][lvl]["max"]
    new_val = current + change
    if 0 <= new_val <= maximum:
        perso["spells"][lvl]["actuel"] = new_val
    make_dirty()

def cb_update_feat(idx, change):
    st.session_state.perso["features"][idx]["actuel"] += change
    st.session_state.perso["features"] = st.session_state.perso["features"]
    make_dirty()

def cb_update_item(idx, change):
    st.session_state.perso["items"][idx]["actuel"] += change
    st.session_state.perso["items"] = st.session_state.perso["items"]
    make_dirty()

def cb_move_item(liste_cle, index, direction):
    liste = st.session_state.perso[liste_cle]
    new_index = index + direction
    if 0 <= new_index < len(liste):
        liste[index], liste[new_index] = liste[new_index], liste[index]
        st.session_state.perso[liste_cle] = st.session_state.perso[liste_cle]
        make_dirty()

def cb_update_dv(change, max_dv):
    current = st.session_state.perso.get("hit_dice_used", 0)
    new_val = current + change
    if 0 <= new_val <= max_dv:
        st.session_state.perso["hit_dice_used"] = new_val
    make_dirty()

def cb_change_classe():
    new_classe = st.session_state.widget_classe
    st.session_state.perso["infos"]["classe"] = new_classe
    make_dirty()

# --- COMPOSANT VISUEL ÉPURÉ (V19) ---
def compteur_propre(label, keys_path, min_val=0, max_val=1000):
    """Un seul champ number_input propre avec callback"""
    val = st.session_state.perso
    for k in keys_path: val = val[k]
    
    widget_key = f"w_clean_{keys_path}"
    
    # On utilise le label natif de Streamlit, plus propre
    st.number_input(label, value=val, min_value=min_val, max_value=max_val, 
                    key=widget_key, on_change=cb_manual_input, args=(keys_path, widget_key))


# --- GESTION ÉTAT ---
if "db" not in st.session_state:
    with st.spinner('Connexion Cloud...'):
        st.session_state.db = charger_donnees()

if "current_char_id" not in st.session_state:
    st.session_state.current_char_id = None
if "unsaved_changes" not in st.session_state:
    st.session_state.unsaved_changes = False
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = {}

# --- ACTIONS ---
def action_sauvegarder():
    nom = st.session_state.perso["infos"]["nom"]
    bm = calculer_bm(st.session_state.perso["infos"]["niveau"])
    for f in st.session_state.perso["features"]:
        if f.get("linked_pb", False):
            f["max"] = bm
            if f["actuel"] > bm: f["actuel"] = bm
    st.session_state.db[nom] = st.session_state.perso
    with st.spinner('Sauvegarde Cloud...'):
        sauvegarder_donnees(st.session_state.db)
    st.session_state.current_char_id = nom
    st.session_state.unsaved_changes = False 
    st.toast(f"Sauvegarde Cloud réussie ! ☁️")
    st.rerun()

def action_supprimer_perso(nom_a_supprimer):
    if nom_a_supprimer in st.session_state.db:
        del st.session_state.db[nom_a_supprimer]
        with st.spinner('Suppression Cloud...'):
            sauvegarder_donnees(st.session_state.db)
        st.toast(f"{nom_a_supprimer} supprimé.")
        st.rerun()

def action_quitter_sans_sauver():
    st.session_state.current_char_id = None
    st.session_state.unsaved_changes = False
    st.rerun()

# --- MODALES ---
@st.dialog("Confirmer la suppression")
def dialog_suppression(nom_perso):
    st.warning(f"Supprimer **{nom_perso}** du Cloud ?")
    col1, col2 = st.columns(2)
    if col1.button("🗑️ Oui", type="primary"): action_supprimer_perso(nom_perso)
    if col2.button("Annuler"): st.rerun()

@st.dialog("Quitter sans sauvegarder ?")
def dialog_confirm_exit():
    st.warning("Vous avez des modifications non enregistrées.")
    col1, col2 = st.columns(2)
    if col1.button("Quitter sans sauver"): action_quitter_sans_sauver()
    if col2.button("Rester"): st.rerun()

@st.dialog("Confirmer le Repos")
def dialog_repos(type_repos):
    st.write(f"Lancer un repos **{type_repos}** ?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Valider", type="primary"):
        if type_repos == "Court":
            for f in st.session_state.perso["features"]:
                if f["repos"] == "Court": f["actuel"] = f["max"]
            for i in st.session_state.perso["items"]:
                if i["repos"] == "Court": i["actuel"] = i["max"]
            st.toast("Repos court terminé")
        else:
            bm = calculer_bm(st.session_state.perso["infos"]["niveau"])
            for f in st.session_state.perso["features"]: 
                if f.get("linked_pb", False): f["max"] = bm
                f["actuel"] = f["max"]
            for i in st.session_state.perso["items"]: 
                i["actuel"] = i["max"]
            for lvl in st.session_state.perso["spells"]:
                st.session_state.perso["spells"][lvl]["actuel"] = st.session_state.perso["spells"][lvl]["max"]
            st.session_state.perso["hit_dice_used"] = 0
            st.session_state.perso["hp"]["actuel"] = st.session_state.perso["hp"]["max"]
            st.session_state.perso["hp"]["temp"] = 0
            st.toast("Repos long terminé")
        st.rerun()
    if col2.button("Annuler"): st.rerun()

# ================= INTERFACE =================

if st.session_state.current_char_id is None:
    st.title("🐉 D&D Manager - V19 (Clean UI)")
    col_g, col_d = st.columns([1, 1])
    with col_g:
        st.subheader("Héros (Google Sheets)")
        liste_persos = list(st.session_state.db.keys())
        if liste_persos:
            for p_nom in liste_persos:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1, 1])
                    info_p = st.session_state.db[p_nom]['infos']
                    c1.markdown(f"**{p_nom}** - {info_p['classe']} {info_p['niveau']}")
                    if c2.button("📂", key=f"load_{p_nom}", help="Charger"):
                        st.session_state.perso = json.loads(json.dumps(st.session_state.db[p_nom]))
                        st.session_state.current_char_id = p_nom
                        st.rerun()
                    if c3.button("🗑️", key=f"del_{p_nom}", help="Supprimer"):
                        dialog_suppression(p_nom)
        else: st.info("Aucun personnage trouvé.")

    with col_d:
        st.subheader("Création")
        nom_new = st.text_input("Nom du personnage")
        if st.button("Créer ✨", type="primary"):
            if nom_new and nom_new not in st.session_state.db:
                st.session_state.perso = nouveau_perso_template()
                st.session_state.perso["infos"]["nom"] = nom_new
                st.session_state.current_char_id = nom_new
                action_sauvegarder() 
            elif nom_new in st.session_state.db: st.error("Ce nom existe déjà !")

else:
    if "hp" not in st.session_state.perso: st.session_state.perso["hp"] = {"max": 10, "actuel": 10, "temp": 0}

    c1, c2, c3 = st.columns([1, 6, 1])
    if c1.button("⬅️ Accueil"):
        if st.session_state.unsaved_changes: dialog_confirm_exit()
        else: action_quitter_sans_sauver()
    
    btn_label = "Sauvegarder ☁️ *" if st.session_state.unsaved_changes else "Sauvegarder ☁️"
    btn_type = "primary" if st.session_state.unsaved_changes else "secondary"
    if c3.button(btn_label, type=btn_type, use_container_width=True): action_sauvegarder()

    st.divider()

    # --- INFOS ---
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
    def dirty_callback(): make_dirty()
    
    st.session_state.perso["infos"]["nom"] = col1.text_input("Nom", st.session_state.perso["infos"]["nom"], on_change=dirty_callback)
    st.session_state.perso["infos"]["race"] = col2.text_input("Race", st.session_state.perso["infos"]["race"], on_change=dirty_callback)
    
    current_class_val = st.session_state.perso["infos"]["classe"]
    idx_class = LISTE_CLASSES.index(current_class_val) if current_class_val in LISTE_CLASSES else 0
    col3.selectbox("Classe", LISTE_CLASSES, index=idx_class, key="widget_classe", on_change=cb_change_classe)

    with col4:
        # V19 : Juste un champ number_input propre
        compteur_propre("Niveau", ["infos", "niveau"], 1, 20)
    
    bm = calculer_bm(st.session_state.perso["infos"]["niveau"])
    col5.metric("Bonus Maîtrise", f"+{bm}")

    # --- POINTS DE VIE (V19 CLEAN) ---
    with st.container(border=True):
        st.markdown("### ❤️ Points de Vie")
        hp1, hp2, hp3 = st.columns(3)
        with hp1: compteur_propre("PV Max", ["hp", "max"], 1, 999)
        with hp2: compteur_propre("PV Actuel", ["hp", "actuel"], -999, 999)
        with hp3: compteur_propre("PV Temporaire", ["hp", "temp"], 0, 999)

        cur = st.session_state.perso["hp"]["actuel"]
        max_pv = st.session_state.perso["hp"]["max"]
        if max_pv > 0:
            ratio = float(cur) / float(max_pv)
            st.progress(max(0.0, min(1.0, ratio)))

    # --- DÉS DE VIE ---
    selected_class = st.session_state.perso["infos"]["classe"]
    die_type = CLASSES_DATA.get(selected_class, "d8")
    dv_max = st.session_state.perso["infos"]["niveau"]
    dv_used = st.session_state.perso.get("hit_dice_used", 0)

    with st.container(border=True):
        cdv1, cdv2, cdv3 = st.columns([2, 4, 2])
        cdv1.markdown(f"### 🎲 Dés de Vie ({die_type})")
        dv_restants = dv_max - dv_used
        cdv2.progress(dv_restants / dv_max if dv_max > 0 else 0)
        cdv2.caption(f"Restants : {dv_restants} / {dv_max}")
        b_dv1, b_dv2 = cdv3.columns(2)
        b_dv1.button("Utiliser", on_click=cb_update_dv, args=(1, dv_max), disabled=(dv_used >= dv_max))
        b_dv2.button("Récup.", on_click=cb_update_dv, args=(-1, dv_max), disabled=(dv_used <= 0))

    st.write("")
    c_rest1, c_rest2 = st.columns(2)
    if c_rest1.button("🍎 Repos Court", use_container_width=True): dialog_repos("Court")
    if c_rest2.button("💤 Repos Long", type="primary", use_container_width=True): dialog_repos("Long")

    st.divider()
    tab_spells, tab_feats, tab_items = st.tabs(["🔮 Sorts", "⚔️ Compétences", "🎒 Inventaire"])

    with tab_spells:
        actif = st.checkbox("Activer Sorts", value=st.session_state.perso["spells_active"])
        if actif != st.session_state.perso["spells_active"]:
            st.session_state.perso["spells_active"] = actif
            make_dirty()
            st.rerun()
        if actif:
            cols = st.columns(3)
            for lvl in range(1, 10):
                lvl_str = str(lvl)
                col_idx = (lvl - 1) % 3
                with cols[col_idx]:
                    with st.container(border=True):
                        st.write(f"**Niveau {lvl}**")
                        old_max = st.session_state.perso["spells"][lvl_str]["max"]
                        def on_change_max_spell(): make_dirty()
                        new_max = st.number_input("Max", 0, 4, value=old_max, key=f"smx_{lvl}", on_change=on_change_max_spell)
                        st.session_state.perso["spells"][lvl_str]["max"] = new_max
                        if st.session_state.perso["spells"][lvl_str]["actuel"] > new_max:
                            st.session_state.perso["spells"][lvl_str]["actuel"] = new_max
                        curr = st.session_state.perso["spells"][lvl_str]["actuel"]
                        display_str = "🟦 " * curr + "⬛ " * (new_max - curr)
                        st.markdown(f"<div style='font-size: 28px; line-height: 1.5; margin-bottom: 10px;'>{display_str}</div>", unsafe_allow_html=True)
                        b1, b2 = st.columns(2)
                        b1.button("Utiliser", key=f"use_{lvl}", on_click=cb_update_spell, args=(lvl_str, -1), disabled=(curr==0))
                        b2.button("Restaurer", key=f"rest_{lvl}", on_click=cb_update_spell, args=(lvl_str, 1), disabled=(curr==new_max))

    with tab_feats:
        with st.expander("Ajouter Compétence"):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            n_name = c1.text_input("Nom", key="nf_name")
            link_pb = c2.checkbox("Lier au BM ?", key="nf_link")
            val_max = bm if link_pb else 1
            n_max = c2.number_input("Max", 1, 50, val_max, disabled=link_pb, key="nf_max")
            n_rest = c3.selectbox("Reset", ["Court", "Long"], key="nf_rest")
            if c4.button("Ajouter", key="nf_add") and n_name:
                st.session_state.perso["features"].append({
                    "nom": n_name, "max": n_max, "actuel": n_max, "repos": n_rest, "linked_pb": link_pb
                })
                make_dirty()
                st.rerun()
        feats = st.session_state.perso["features"]
        for i, feat in enumerate(feats):
            with st.container(border=True):
                if st.session_state.edit_mode.get(f"feat_{i}", False):
                    ec1, ec2, ec3, ec4 = st.columns([3, 1, 1, 1])
                    new_nom = ec1.text_input("Nom", feat["nom"], key=f"ed_n_{i}")
                    edit_link = ec2.checkbox("Lier BM", value=feat.get("linked_pb", False), key=f"ed_l_{i}")
                    edit_max_val = bm if edit_link else feat["max"]
                    edit_max = ec2.number_input("Max", 1, 50, edit_max_val, disabled=edit_link, key=f"ed_m_{i}")
                    edit_rest = ec3.selectbox("Reset", ["Court", "Long"], index=0 if feat["repos"]=="Court" else 1, key=f"ed_r_{i}")
                    if ec4.button("💾 Sauver", key=f"ed_save_{i}"):
                        feat["nom"] = new_nom
                        feat["linked_pb"] = edit_link
                        feat["max"] = edit_max
                        feat["repos"] = edit_rest
                        st.session_state.edit_mode[f"feat_{i}"] = False
                        make_dirty()
                        st.rerun()
                else:
                    c_top1, c_top2 = st.columns([4, 2])
                    badges = f"({feat['repos']})"
                    if feat.get("linked_pb"): badges += " [Lien BM]"
                    c_top1.write(f"**{feat['nom']}** {badges}")
                    
                    b_edit, b_del, b_up, b_down = c_top2.columns(4)
                    if b_edit.button("✍️", key=f"ed_{i}"):
                        st.session_state.edit_mode[f"feat_{i}"] = True
                        st.rerun()
                    if b_del.button("🗑️", key=f"del_{i}"):
                        st.session_state.perso["features"].pop(i)
                        make_dirty()
                        st.rerun()
                    if i > 0: 
                        b_up.button("⬆️", key=f"up_{i}", on_click=cb_move_item, args=("features", i, -1))
                    if i < len(feats) - 1:
                        b_down.button("⬇️", key=f"down_{i}", on_click=cb_move_item, args=("features", i, 1))

                    if feat['max'] > 0: st.progress(feat['actuel'] / feat['max'])

                    c_act1, c_act2 = st.columns(2)
                    c_act1.button("Utiliser", key=f"use_feat_{i}", on_click=cb_update_feat, args=(i, -1), disabled=(feat['actuel']==0), use_container_width=True)
                    c_act2.button("Restaurer", key=f"rest_feat_{i}", on_click=cb_update_feat, args=(i, 1), disabled=(feat['actuel']==feat['max']), use_container_width=True)
                    st.markdown(f"<div style='text-align: center;'>{feat['actuel']} / {feat['max']}</div>", unsafe_allow_html=True)

    with tab_items:
        with st.expander("Ajouter Objet"):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            i_name = c1.text_input("Nom", key="ni_name")
            i_max = c2.number_input("Charges", 1, 50, 1, key="ni_max")
            i_rest = c3.selectbox("Reset", ["Court", "Long", "Jamais"], key="ni_rest")
            if c4.button("Ajouter", key="ni_add") and i_name:
                st.session_state.perso["items"].append({"nom": i_name, "max": i_max, "actuel": i_max, "repos": i_rest})
                make_dirty()
                st.rerun()
        items = st.session_state.perso["items"]
        if not items: st.info("Inventaire vide.")
        for i, item in enumerate(items):
            with st.container(border=True):
                c_top1, c_top2 = st.columns([4, 2])
                c_top1.write(f"**{item['nom']}** ({item['repos']})")
                
                b_del, b_up, b_down = c_top2.columns([1, 1, 1])
                if b_del.button("🗑️", key=f"del_i_{i}"):
                    st.session_state.perso["items"].pop(i)
                    make_dirty()
                    st.rerun()
                if i > 0: b_up.button("⬆️", key=f"up_i_{i}", on_click=cb_move_item, args=("items", i, -1))
                if i < len(items) - 1: b_down.button("⬇️", key=f"down_i_{i}", on_click=cb_move_item, args=("items", i, 1))

                if item['max'] > 0: st.progress(item['actuel'] / item['max'])

                c_act1, c_act2 = st.columns(2)
                c_act1.button("Utiliser", key=f"use_item_{i}", on_click=cb_update_item, args=(i, -1), disabled=(item['actuel']==0), use_container_width=True)
                c_act2.button("Restaurer", key=f"rest_item_{i}", on_click=cb_update_item, args=(i, 1), disabled=(item['actuel']==item['max']), use_container_width=True)
                st.markdown(f"<div style='text-align: center;'>{item['actuel']} / {item['max']}</div>", unsafe_allow_html=True)