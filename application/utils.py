##################################################################################
#                                                                                #
# Copyright (c) 2020 AECgeeks                                                    #
#                                                                                #
# Permission is hereby granted, free of charge, to any person obtaining a copy   #
# of this software and associated documentation files (the "Software"), to deal  #
# in the Software without restriction, including without limitation the rights   #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell      #
# copies of the Software, and to permit persons to whom the Software is          #
# furnished to do so, subject to the following conditions:                       #
#                                                                                #
# The above copyright notice and this permission notice shall be included in all #
# copies or substantial portions of the Software.                                #
#                                                                                #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR     #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,       #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE    #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER         #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,  #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE  #
# SOFTWARE.                                                                      #
#                                                                                #
##################################################################################

import os
import string
import tempfile
import requests

from random import SystemRandom
choice = lambda seq: SystemRandom().choice(seq)
letter_set = set(string.ascii_letters)

STORAGE_DIR = os.environ.get("MODEL_DIR", tempfile.gettempdir()) 

def generate_id():
    return "".join(choice(string.ascii_letters) for i in range(32))


def storage_dir_for_id(id):
    id = id.split("_")[0]
    return os.path.join(STORAGE_DIR, id[0:1], id[0:2], id[0:3], id)


def storage_file_for_id(id, ext):
    return os.path.join(storage_dir_for_id(id), id + "." + ext)


def validate_id(id):
    id_num = id.split("_")
    
    if len(id_num) == 1:
        id = id_num[0]
    elif len(id_num) == 2:
        id, num = id_num
        num = str(int(num))
    else:
        return False

    return len(set(id) - set(string.ascii_letters)) == 0


def unconcatenate_ids(id):
    return [id[i:i+32] for i in range(0, len(id), 32)]


def send_message(msg_content, user_email, html=None):
    dom = os.getenv("SERVER_NAME")
    base_url = f"https://api.eu.mailgun.net/v3/{dom}/messages"
    from_ = f"Validation Service <noreply.validate@{dom}>"
    
    return requests.post(
        base_url,
        auth=("api", os.getenv("MG_KEY")),

        data={"from": from_,
              "to": user_email,
              "html":html,
              "subject": "Validation Service update",
              "text": msg_content})
