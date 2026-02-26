import asyncio
import os
from curl_cffi import requests
from bs4 import BeautifulSoup
import discord
from db_manager import remove_from_queue

STUDEFI_URL = "https://www.studefi.fr/main.php"

def ensure_dummy_pdf():
    pdf_path = "dummy_id.pdf"
    if not os.path.exists(pdf_path):
        dummy_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
        with open(pdf_path, 'wb') as f:
            f.write(dummy_content)
    return pdf_path

def generate_random_data(email):
    return {
        "email": email,
        "civilite": "Monsieur",
        "nom": "Dupont",
        "prenom": "Jean",
        "date_naissance": "01/01/2000",
        "lieu_naissance": "Paris",
        "situation_famille": "Célibataire",
        "adresse": "1 rue de la Paix",
        "code_postal": "75001",
        "ville": "Paris",
        "pays": "484", # France
        "telephone": "0600000000",
        "situation": "Etudiant",
        "etudes": "Licence",
        "etablissement": "Université",
        "boursier": "0",
        "job": "0",
        
        # Garant
        "garant_nom": "Dupont",
        "garant_prenom": "Pierre",
        "garant_date_naissance": "01/01/1970",
        "garant_lieu_naissance": "Paris",
        "garant_lien": "Père / Mère",
        "garant_adresse": "1 rue de la Paix",
        "garant_cp": "75001",
        "garant_ville": "Paris",
        "garant_telephone": "0600000001",
        "garant_email": "dupont.pierre@example.com",
        "garant_profession": "Employé",
        "garant_personnes": "0",
        "garant_logement": "Propriétaire",
        "garant_depuis": "01/01/2010",
        "garant_loyer": "1000",
        "garant_revenus": "3000",
        "garant_charges": "500"
    }

async def process_queue_for_residence(name, link, queue_users, bot):
    """Attempt to reserve an apartment for the first matching user in queue."""
    # Find matching user
    target_user = None
    for user_id, q_residence, email, _ in queue_users:
        if q_residence.lower() == "first available" or q_residence.lower() in name.lower() or name.lower() in q_residence.lower():
            target_user = (user_id, email)
            break
            
    if not target_user:
        return
        
    user_id, email = target_user
    pdf_path = ensure_dummy_pdf()
    session = requests.AsyncSession(impersonate="chrome")
    
    try:
        # Step 1: Parse Residence Page to get reservation link
        residence_url = f"https://www.studefi.fr/{link}" if not link.startswith("http") else link
        res = await session.get(residence_url)
        soup = BeautifulSoup(res.text, "html.parser")
        
        reserver_link = None
        for a in soup.find_all("a", class_="button mini-button"):
            if "Réserver en ligne" in a.get_text() or "srv=Reservation" in a.get("href", ""):
                reserver_link = a.get("href")
                break
                
        if not reserver_link:
            print(f"No reservation button found for {name}")
            return
            
        if not reserver_link.startswith("http"):
            reserver_link = f"https://www.studefi.fr/{reserver_link.lstrip('/')}"
            
        print(f"[{email}] Started reservation for {name}: {reserver_link}")
        
        # Step 2: GET Studefi_1.html to extract hidden fields
        res1 = await session.get(reserver_link)
        soup1 = BeautifulSoup(res1.text, "html.parser")
        form1 = soup1.find("form", id="form1")
        if not form1:
            print("Form 1 not found.")
            return
            
        def get_hidden_val(soup_form, field_name):
            inp = soup_form.find("input", {"name": field_name})
            return inp.get("value", "") if inp else ""
            
        data = generate_random_data(email)
        
        payload1 = {
            "tokenCSRF": get_hidden_val(form1, "tokenCSRF"),
            "srv": get_hidden_val(form1, "srv"),
            "op": "saveEtape1",
            "cdTemporaire": get_hidden_val(form1, "cdTemporaire"),
            "cdEsi": get_hidden_val(form1, "cdEsi"),
            "idDemandeLogement": get_hidden_val(form1, "idDemandeLogement"),
            "idLogement": get_hidden_val(form1, "idLogement"),
            "lbEmail": data["email"],
            "lbCivilite": data["civilite"],
            "lbNom": data["nom"],
            "lbPrenom": data["prenom"],
            "dtNaissance": data["date_naissance"],
            "lbLieuNaissance": data["lieu_naissance"],
            "cdSituationFamille": data["situation_famille"],
            "lbAdresse": data["adresse"],
            "cdPostal": data["code_postal"],
            "lbVille": data["ville"],
            "idPays": data["pays"],
            "nbTelephone": data["telephone"],
            "lbSituation": data["situation"],
            "lbPrecisionSituation": "",
            "lbTypeEtudes": data["etudes"],
            "lbNomEtablissement": data["etablissement"],
            "fgBoursier": data["boursier"],
            "fgJobEtudiant": data["job"],
            "button": "Etape suivante"
        }
        
        with open(pdf_path, 'rb') as f:
            files1 = {'pieceIdentite': ('piece.pdf', f, 'application/pdf')}
            submit1 = await session.post(
                "https://www.studefi.fr/main.php",
                data=payload1,
                files=files1
            )
            
        # Step 3: Parse Studefi_2.html
        soup2 = BeautifulSoup(submit1.text, "html.parser")
        form2 = soup2.find("form", id="form1")
        if not form2:
            print("Form 2 not found.")
            return
            
        payload2 = {
            "tokenCSRF": get_hidden_val(form2, "tokenCSRF"),
            "srv": get_hidden_val(form2, "srv"),
            "op": "saveEtape2",
            "cdTemporaire": get_hidden_val(form2, "cdTemporaire"),
            "cdEsi": get_hidden_val(form2, "cdEsi"),
            "etapePrecedente": get_hidden_val(form2, "etapePrecedente"),
            "idDemandeLogement": get_hidden_val(form2, "idDemandeLogement"),
            "idLogement": get_hidden_val(form2, "idLogement"),
            "lbCiviliteGarant": data["civilite"],
            "lbNomGarant": data["garant_nom"],
            "lbPrenomGarant": data["garant_prenom"],
            "dtNaissanceGarant": data["garant_date_naissance"],
            "lbLieuNaissanceGarant": data["garant_lieu_naissance"],
            "cdSituationFamilleGarant": data["situation_famille"],
            "cdLienParenteGarant": data["garant_lien"],
            "lbAdresseGarant": data["garant_adresse"],
            "cdPostalGarant": data["garant_cp"],
            "lbVilleGarant": data["garant_ville"],
            "idPaysGarant": data["pays"],
            "nbTelephoneGarant": data["garant_telephone"],
            "lbEmailGarant": data["garant_email"],
            "lbProfessionGarant": data["garant_profession"],
            "nbPersonnesAChargeGarant": data["garant_personnes"],
            "lbLocataireProprietaireGarant": data["garant_logement"],
            "dtDebutProprietaireGarant": data["garant_depuis"],
            "nbMontantLoyerGarant": data["garant_loyer"],
            "nbRevenusGarant": data["garant_revenus"],
            "nbMoisRevenusGarant": "12",
            "lbPrecisionRevenusGarant": "CDI",
            "nbChargesGarant": data["garant_charges"],
            "button": "Etape suivante"
        }
        
        with open(pdf_path, 'rb') as f:
            files2 = {'pieceIdentiteGarant': ('pieceGarant.pdf', f, 'application/pdf')}
            submit2 = await session.post(
                "https://www.studefi.fr/main.php",
                data=payload2,
                files=files2
            )
            
        # Step 4: Verification
        if "Confirmation" in submit2.text or "confirmation" in submit2.url.lower() or "etape 3" in submit2.text.lower() or "etape3" in submit2.text.lower() or "saveEtape2" not in submit2.text:
            print(f"[{email}] Successfully reached confirmation page!")
            # Remove from queue
            remove_from_queue(user_id)
            
            # Notify User
            user_target = await bot.fetch_user(user_id)
            if user_target:
                embed = discord.Embed(
                    title="🎉 Studefi Reservation Successful!",
                    description=f"Your automated reservation on **{name}** has been submitted.",
                    color=0x00ff00
                )
                embed.add_field(name="Next Steps", value="Check your email for the confirmation link from Studefi!", inline=False)
                await user_target.send(embed=embed)
        else:
            print(f"[{email}] Reservation incomplete, still on step 2 or error.")

    except Exception as e:
        print(f"Exception during reservation for {user_id}: {e}")
    finally:
        await session.close()
