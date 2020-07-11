# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

from os import path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

def check_keys_exsist(privkey, pubkey):
    '''
    check existance of keys
    '''
    if path.exists(privkey) and path.exists(pubkey):
        return True
    else:
        return False

def generate_keys(privkey, pubkey):
    '''
    generate key pair for database encryption
    '''
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(privkey, 'wb') as f:
        f.write(pem)
        
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(pubkey, 'wb') as f:
        f.write(pem)

def get_public_key(pubkey):
    '''load public key'''
    with open(pubkey, 'rb') as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend=default_backend()
        )
    return public_key

def get_private_key(privkey):
    '''load private key'''
    with open(privkey, 'rb') as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )
    return private_key

def encrypt_string(content, _pubkey):
    '''
    encrypt string given by content and return result 
    '''
    public_key = get_public_key(_pubkey)

    encrypted = public_key.encrypt(
        content.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted

def decrypt_string(content, _privkey):
    '''
    decrypt string given by content and return result 
    '''
    try:
        private_key = get_private_key(_privkey)
        decrypted = private_key.decrypt(
            content,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted
    except Exception as e:
        print(e) 