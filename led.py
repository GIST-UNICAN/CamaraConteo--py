#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 29 15:30:00 2019

@author: andres
"""

import Jetson.GPIO as GPIO
import json
from time import sleep
import requests
from requests.exceptions import ConnectionError
from subprocess import Popen, PIPE


output_pin = 18 
contador=0
#al iniciar el script en el boot vamos a parar el opendatacam y arrancarlo
#orden_cierra_docker="sudo docker stop $(sudo docker ps -a -q)"
#orden_abre_archivo="sudo ./run-opendatacam.sh"
#ordenes=(orden_cierra_docker,orden_abre_archivo)
#for orden in ordenes:
#    print('lanzando el comando:', orden)
#    with Popen([orden], stdout=PIPE, shell=True) as proc:
#        print(proc.stdout.read())

# se va a intentar sacar las rallas marcadas y redibujarlas

url_nano='http://192.168.31.108:8080'
url_tablet='http://10.42.0.219:8081'

def post_mensaje(msg,titulo='SERVICIO CAM'):
    try:
        requests.post(url_tablet,data={"title":msg, "text":titulo})
    except:
        pass

def extrae_rayas():
    response=requests.get(f'{url_nano}/counter/areas')
    rayas = json.loads(response.text)
    post_mensaje('extrae rayas:', response.status_code)
    print('extrae rayas:', response.status_code)
    return rayas

def redibuja_rayas(json_rayas):
    headers = {'content-type': 'application/json'}
    json_sube=json.dumps({'countingAreas':json_rayas})
    response=requests.post(f'{url_nano}/counter/areas', data=json_sube,headers=headers)
    print("Codigo de rayas:",response.status_code)

redibuja_rayas(extrae_rayas())

def ejecuta_consola(comando):
    with Popen([comando], stdout=PIPE, shell=True, encoding='utf8') as proc:
        lectura=proc.stdout.read()
    return lectura

# extraer memoria Swap restante
def memoria_swap_libre(comando_consola='free -m | grep Swap'):
    lectura=ejecuta_consola(comando_consola).split()
    mem_total=int(lectura[1])
    mem_libre=int(lectura[-1])
    return mem_libre/mem_total

def reinicia_opendatacam(comando_consola='sudo pm2 restart opendatacam', 
                         json_config='{"counterEnabled": 1, '
                         '"pathfinderEnabled": 0}'):
    rayas=extrae_rayas()
    ejecuta_consola(comando_consola)
    while True:
        try:
            response=requests.get(f'{url_nano}/start')
            post_mensaje('reinicio:',response.status_code)
            print('reinicio:',response.status_code)
            if response.status_code==200: break
        except ConnectionError:
            post_mensaje('error al lanzar opendatacam, reintentando...')
            print('error al lanzar opendatacam, reintentando...')
            sleep(1)
#    
    if response.status_code==200:
        
        while True:
            response=requests.get(f'{url_nano}/recording/start')
            if response.status_code==200:
                requests.get(f'{url_nano}/recording/stop')
                headers = {'content-type': 'application/json'}
                response=requests.post(f"{url_nano}/ui", data=json_config,headers=headers)  
                post_mensaje('config:',response.status_code)
                print('config:',response.status_code)
                redibuja_rayas(rayas)
                requests.get(f'{url_nano}/recording/start')
                break           
            else:
                post_mensaje('Error, no se detectan objetos aun ...')
                requests.get(f'{url_nano}/recording/stop')
                print('Error, no se detectan objetos aun ...')
                sleep(1)
        post_mensaje('inicio grabacion:',response.status_code)        
        print('inicio grabacion:',response.status_code)
  

# Pin Seºtup:
# Board pin-numbering scheme
GPIO.setmode(GPIO.BCM)
# set pin as an output pin with optional initial state of HIGH
GPIO.setup(output_pin, GPIO.OUT, initial=GPIO.HIGH)
encendido = GPIO.HIGH
apagado = GPIO.LOW
GPIO.output(18, apagado)


while True:
    try:
        conteo = requests.get("http://localhost:8080/status")
        conteo = json.loads(conteo.text)
        conteo = next(iter(conteo['counterSummary'].values()))['_total']
        if conteo > contador:
            print('objeto detectado')
            #enciende led
            GPIO.output(18, encendido)
            contador=conteo
    except StopIteration:
        pass
    except ConnectionError:
        print('Intentando reconectar')
        sleep(4)
    memoria_libre=memoria_swap_libre()
    print('memoria_libre:', memoria_libre)
    
    if memoria_swap_libre() < 0.1: 
        post_mensaje(f'la memoria esta al {1-memoria_libre}, reiniciando...')
        reinicia_opendatacam()
        
    sleep(1)
    GPIO.output(18, apagado)
