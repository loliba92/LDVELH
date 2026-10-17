"""Tests de la vérification d'identité Google.   python pipeline/test_identite.py"""
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identite
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

CLIENT = "123-abc.apps.googleusercontent.com"
ADMINS = {"Marc.Dupont@gmail.com": "Marc"}


def fabrique():
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update(kid="k1", alg="RS256", use="sig")
    return cle, {"keys": [jwk]}


def jeton(cle, **sur):
    infos = {"iss": "https://accounts.google.com", "aud": CLIENT, "exp": int(time.time()) + 600, "email": "marc.dupont@gmail.com", "email_verified": True}
    infos.update(sur)
    infos = {k: v for k, v in infos.items() if v is not None}
    return jwt.encode(infos, cle, algorithm="RS256", headers={"kid": "k1"})


class TestIdentite(unittest.TestCase):
    def setUp(self):
        self.cle, self.certs = fabrique()

    def v(self, j, **kw):
        return identite.verifier(j, kw.get("client", CLIENT), ADMINS, self.certs)

    def test_admin_reconnu_sans_tenir_compte_de_la_casse(self):
        self.assertEqual(self.v(jeton(self.cle)), ("Marc", None))

    def test_adresse_donnee_par_son_empreinte(self):
        import hashlib
        h = "sha256:" + hashlib.sha256(b"marc.dupont@gmail.com").hexdigest()
        self.assertEqual(identite.verifier(jeton(self.cle), CLIENT, {h: "Marc"}, self.certs), ("Marc", None))

    def test_refus(self):
        autre, _ = fabrique()
        cas = {
            "aucun": "",
            "mauvaise signature": jeton(autre),
            "autre site": jeton(self.cle, aud="autre"),
            "expiré": jeton(self.cle, exp=int(time.time()) - 3600),
            "adresse inconnue": jeton(self.cle, email="intrus@gmail.com"),
            "adresse non vérifiée": jeton(self.cle, email_verified=False),
            "autre émetteur": jeton(self.cle, iss="https://evil.example"),
            "texte quelconque": "abc.def.ghi",
        }
        for nom, j in cas.items():
            with self.subTest(nom):
                self.assertIsNone(self.v(j)[0])
                self.assertTrue(self.v(j)[1])

    def test_jeton_non_signe_refuse(self):
        j = jwt.encode({"iss": "accounts.google.com", "aud": CLIENT, "exp": int(time.time()) + 600, "email": "marc.dupont@gmail.com", "email_verified": True}, None, algorithm="none", headers={"kid": "k1"})
        self.assertIsNone(self.v(j)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
