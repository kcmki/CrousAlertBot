import asyncio
import os
import sys
import logging
import curl_cffi
from curl_cffi import requests

from bs4 import BeautifulSoup

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
        "type_etablissement": "Université",
        "filiere": "Informatique",
        "etablissement": "Université de Paris",
        "boursier": "0",
        "job": "0",
        
        # Colocataire (if required, sending dummy data)
        "coloc_email": "coloc@example.com",
        "coloc_civilite": "Monsieur",
        "coloc_nom": "Martin",
        "coloc_prenom": "Paul",
        "coloc_date_naissance": "02/02/2000",
        "coloc_ville_naissance": "Lyon",
        "coloc_situation_famille": "Célibataire",
        "coloc_adresse": "2 rue de la Paix",
        "coloc_cp": "75002",
        "coloc_ville": "Paris",
        "coloc_pays": "484", # France
        "coloc_telephone": "0600000002",
        "coloc_situation": "Etudiant",
        "coloc_etudes": "Licence",
        "coloc_type_etablissement": "Université",
        "coloc_etablissement": "Université de Paris",
        "coloc_filiere": "Mathématiques",
        "coloc_boursier": "0",
        "coloc_job": "0",
        
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
        "garant_charges": "500",
        "garant_allocations": "0",
        "garant_autres_revenus": "0"
    }

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

async def get_available_residences():
    """Scrapes Studefi for available residences similarly to the main bot loop."""
    logger.info("Checking Studefi for available residences...")
    session = requests.AsyncSession(impersonate="chrome")
    try:
        response = await session.get("https://www.studefi.fr/main.php")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            elements = soup.find_all("div", class_="col-sm-6 list-res-elem")
            
            available = []
            for elem in elements:
                img_tag = elem.find("img", class_="dispoRes")
                if img_tag:
                    img_src = img_tag.get("src", "")
                    if "non_disponibles" not in img_src:
                        name_tag = elem.find("div", class_="list-res-link").find("a")
                        name = name_tag.get_text(strip=True)
                        link = name_tag.get("href", "")
                        available.append((name, link))
            
            logger.info(f"Found {len(available)} available residence(s).")
            return available
        else:
            logger.error(f"Failed to check Studefi, status code: {response.status_code}")
            return []
    except Exception as e:
        logger.exception(f"Error checking Studefi: {e}")
        return []
    finally:
        await session.close()

async def test_reservation(name, link, email):
    logger.info(f"Starting test reservation for '{name}' with email '{email}'")
    logger.info(f"Target link: {link}")
    
    pdf_path = ensure_dummy_pdf()
    session = requests.AsyncSession(impersonate="chrome")
    
    try:
        # Step 1: Parse Residence Page to get reservation link
        residence_url = f"https://www.studefi.fr/{link}" if not link.startswith("http") else link
        logger.debug(f"GET Request to Residence URL: {residence_url}")
        res = await session.get(residence_url)
        
        if res.status_code != 200:
            logger.error(f"Failed to load residence page, status code: {res.status_code}")
            return

        with open("debug_residence_page.html", "w", encoding="utf-8") as f_debug:
            f_debug.write(res.text)
            
        soup = BeautifulSoup(res.text, "html.parser")
        
        reserver_link = None
        for a in soup.find_all("a", class_="button mini-button"):
            if "Réserver en ligne" in a.get_text() or "srv=Reservation" in a.get("href", ""):
                reserver_link = a.get("href")
                break
                
        if not reserver_link:
            logger.error(f"No reservation button found for '{name}' on the page (maybe it's not actually available).")
            return
            
        if not reserver_link.startswith("http"):
            reserver_link = f"https://www.studefi.fr/{reserver_link.lstrip('/')}"
            
        logger.info(f"✅ Found reservation link: {reserver_link}")
        
        # Step 2: GET Step 1 form to extract hidden fields
        logger.debug(f"GET Request to Step 1 form: {reserver_link}")
        res1 = await session.get(reserver_link)
        
        with open("debug_step1_page.html", "w", encoding="utf-8") as f_debug:
            f_debug.write(res1.text)
            
        soup1 = BeautifulSoup(res1.text, "html.parser")
        form1 = soup1.find("form", id="form1")
        if not form1:
            logger.error("❌ Form 1 not found on the reservation page.")
            return
            
        def get_hidden_val(soup_form, field_name):
            inp = soup_form.find("input", {"name": field_name})
            val = inp.get("value", "") if inp else ""
            logger.debug(f"Extracted hidden field '{field_name}': {val}")
            return val
            
        logger.info("Generating random user data...")
        data = generate_random_data(email)
        
        logger.info("Extracting hidden fields for Step 1 payload...")
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
            "lbVilleNaissance": data["lieu_naissance"],
            "cdSituationFamille": data["situation_famille"],
            "lbAdresse": data["adresse"],
            "cdPostal": data["code_postal"],
            "lbVille": data["ville"],
            "idPays": data["pays"],
            "nbTelephone": data["telephone"],
            "lbSituation": data["situation"],
            "lbEtudes": data["etudes"],
            "lbTypeEtablissement": data["type_etablissement"],
            "lbNomEtablissement": data["etablissement"],
            "lbFiliere": data["filiere"],
            "fgBoursier": data["boursier"],
            "fgJobEtudiant": data["job"],
            
            # Colocataire Data
            "lbEmailColocataire": data["coloc_email"],
            "lbCiviliteColocataire": data["coloc_civilite"],
            "lbNomColocataire": data["coloc_nom"],
            "lbPrenomColocataire": data["coloc_prenom"],
            "dtNaissanceColocataire": data["coloc_date_naissance"],
            "lbVilleNaissanceColocataire": data["coloc_ville_naissance"],
            "cdSituationFamilleColocataire": data["coloc_situation_famille"],
            "lbAdresseColocataire": data["coloc_adresse"],
            "cdPostalColocataire": data["coloc_cp"],
            "lbVilleColocataire": data["coloc_ville"],
            "idPaysColocataire": data["coloc_pays"],
            "nbTelephoneColocataire": data["coloc_telephone"],
            "lbSituationColocataire": data["coloc_situation"],
            "lbEtudesColocataire": data["coloc_etudes"],
            "lbTypeEtablissementColocataire": data["coloc_type_etablissement"],
            "lbNomEtablissementColocataire": data["coloc_etablissement"],
            "lbFiliereColocataire": data["coloc_filiere"],
            "fgBoursierColocataire": data["coloc_boursier"],
            "fgJobEtudiantColocataire": data["coloc_job"],
            
            "button": "Etape suivante"
        }
        
        # Dynamically extracting the POST tracking URL
        action_url1 = form1.get("action")
        if not action_url1:
            action_url1 = "https://www.studefi.fr/main.php"
        elif not action_url1.startswith("http"):
            action_url1 = f"https://www.studefi.fr/{action_url1.lstrip('/')}"
        
        logger.info(f"🚀 Submitting Step 1 to: {action_url1}")
        
        mp1 = curl_cffi.CurlMime()
        mp1.addpart(name="pieceIdentite", content_type="application/pdf", filename="piece.pdf", local_path=pdf_path)
        mp1.addpart(name="pieceIdentiteColocataire", content_type="application/pdf", filename="piece_coloc.pdf", local_path=pdf_path)
        
        submit1 = await session.post(
            action_url1,
            data=payload1,
            multipart=mp1
        )
        mp1.close()
            
        logger.info(f"Step 1 Submit Status Code: {submit1.status_code}")
        logger.debug(f"Step 1 Redirect URL: {submit1.url}")

        # Step 3: Parse the response for Studefi_2.html
        with open("debug_step2_page.html", "w", encoding="utf-8") as f_debug:
            f_debug.write(submit1.text)
            
        soup2 = BeautifulSoup(submit1.text, "html.parser")
        form2 = soup2.find("form", id="form1")
        if not form2:
            logger.error("❌ Form 2 not found on the next page. Submission might have failed or redirected unexpectedly.")
            # For debugging, preserve the HTML
            with open("debug_step1_response.html", "w", encoding="utf-8") as f_debug:
                f_debug.write(submit1.text)
            logger.info("Saved the failed response HTML to 'debug_step1_response.html' for analysis.")
            return

        logger.info("✅ Successfully reached Step 2. Extracting fields...")
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
            "nbAllocationsFamilialesGarant": data["garant_allocations"],
            "nbAutresRevenusGarant": data["garant_autres_revenus"],
            "button": "Etape suivante"
        }
        
        # Dynamically extracting the POST tracking URL again
        action_url2 = form2.get("action")
        if not action_url2:
            action_url2 = "https://www.studefi.fr/main.php"
        elif not action_url2.startswith("http"):
            action_url2 = f"https://www.studefi.fr/{action_url2.lstrip('/')}"
            
        logger.info(f"🚀 Submitting Step 2 to: {action_url2}")
        
        mp2 = curl_cffi.CurlMime()
        mp2.addpart(name="pieceIdentiteGarant", content_type="application/pdf", filename="pieceGarant.pdf", local_path=pdf_path)
        
        submit2 = await session.post(
            action_url2,
            data=payload2,
            multipart=mp2
        )
        mp2.close()
            
        logger.info(f"Step 2 Submit Status Code: {submit2.status_code}")
        logger.debug(f"Step 2 Redirect URL: {submit2.url}")
        
        # Step 4: Verification
        success_marker = 'value="Valider ma demande"'
        if success_marker in submit2.text:
            with open("debug_success_page.html", "w", encoding="utf-8") as f_debug:
                f_debug.write(submit2.text)
            logger.info("🎉 SUCCESS! Successfully reached confirmation page!")
            logger.info("Saved the success response HTML to 'debug_success_page.html'.")
        else:
            logger.warning("❌ Reservation incomplete, still on step 2 or error.")
            with open("debug_step2_response.html", "w", encoding="utf-8") as f_debug:
                f_debug.write(submit2.text)
            logger.info("Saved the failed response HTML to 'debug_step2_response.html' for analysis.")

    except Exception as e:
        logger.exception(f"Exception during reservation: {e}")
    finally:
        await session.close()
        logger.info("🏁 Test finished.")

async def main():
    logger.info("=" * 60)
    logger.info("Starting standalone Studefi reservation debug script...")
    logger.info("=" * 60)
    
    TEST_EMAIL = "[email protected]"
    
    # Enable automatic detection of available residences
    residences = await get_available_residences()
    
    if not residences:
        logger.error("No available residences found right now.")
        return
        
    # Pick the first available one to test
    target_name, target_link = residences[0]
    logger.info(f"Automatically selected available residence for testing:")
    logger.info(f" -> Name: {target_name}")
    logger.info(f" -> Link: {target_link}")
    
    await test_reservation(target_name, target_link, TEST_EMAIL)

if __name__ == "__main__":
    asyncio.run(main())
