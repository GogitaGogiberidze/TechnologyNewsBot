#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
Created on May 20, 2017

@author: gogita.gogiberidze
'''

import logging
import time
import sys
import json
import os
import cf_deployment_tracker
import dotenv
import pandas as pd
import retinasdk

import re
import watson_developer_cloud.natural_language_understanding.features.v1 as features
from watson_developer_cloud.watson_developer_cloud_service import WatsonException

from slackclient import SlackClient
from watson_developer_cloud import ConversationV1
from watson_developer_cloud import NaturalLanguageUnderstandingV1

import swiftclient
import io


  
sys.path.append(os.path.join(os.getcwd(),'..','..'))



# logging.basicConfig(level=logging.DEBUG)
# LOG = logging.getLogger(__name__)


FILE_TECHNOLOGIES = "technologies.csv"
FILE_TECHNOLOGIES_FPRINT = "technologies_fprint.csv"
FILE_COMPANIES  = "companies.csv"
FILE_TECHNOLOGIES_RANK = "Technologies_rank.csv"
FILE_FILTERS_LIST = "filters_list.csv"

# FILE_CATEGFILTER_MATURITY = "categoryfilters_maturity.csv"
# FILE_CATEGFILTER_ENV = "categoryfilters_env.csv"
# FILE_CATEGFILTER_SOLAR = "categoryfilters_solar.csv"
# FILE_CATEGFILTER_AI = "categoryfilters_artificial.csv"
# FILE_CATEGFILTER_ML = "categoryfilters_ML.csv"
# FILE_CATEGFILTER_SOLARPAV = "categoryfilters_solarpav.csv"
OBJSTOR_CONETEINER = "Cortical-data"

FILE_CATEGFILTER_LIST = [{"AI": "categoryfilters_artificial.csv"}, 
                         {"ML": "categoryfilters_ML.csv"}, 
                         {"SOLAR": "categoryfilters_solar.csv"},
                         {"SOLARPAV": "categoryfilters_solarpav.csv"}, 
                         {"MATURITY": "categoryfilters_maturity.csv"}, 
                         {"ENVIRONMENT": "categoryfilters_env.csv"} ]

gv_nlu = None
gv_cortical_client = None
gv_bot_deafault_channel_name = None 
gv_bot_deafault_channel_id = None
gv_objstore_conn = None

def get_vcap_credentials(vcap_env, service):
    if service in vcap_env:
        vcap_conversation = vcap_env[service]
        if isinstance(vcap_conversation, list):
            first = vcap_conversation[0]
            if 'credentials' in first:
                return first['credentials']

                
def init_connections():
    ''' Function to get credentials and initiate all connections 
    return (workspace_id, bot_id, conversation_client, slack_client) '''
    global gv_nlu, gv_cortical_client, gv_bot_deafault_channel_name, gv_bot_deafault_channel_id, gv_objstore_conn
     
    # loading credentials from the file in case environmental variables are not set
    dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "config.env")) 
        
    # Read credentials from env variable first and if not set read from config file
    # Watson conversation: "Conversation_KEEP", workspace - slackbotwatson
    conversation_username = os.environ.get("CONVERSATION_USERNAME_1", os.getenv("CONVERSATION_USERNAME_F"))
    conversation_password = os.environ.get("CONVERSATION_PASSWORD_1", os.getenv("CONVERSATION_PASSWORD_F"))
    workspace_id = os.environ.get("WORKSPACE_ID_1", os.getenv("WORKSPACE_ID_F"))
    
    # Slack: team - aesnewenergysolutions
    bot_id = os.environ.get("SLACK_BOT_USER_1", os.getenv("SLACK_BOT_USER_F"))
    bot_name = os.environ.get("SLACK_BOT_USER_NAME_1", os.getenv("SLACK_BOT_USER_NAME_F"))
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN_1", os.getenv("SLACK_BOT_TOKEN_F"))
    gv_bot_deafault_channel_name = os.environ.get("SLACK_BOT_DEFAULT_CHANNEL_1", os.getenv("SLACK_BOT_DEFAULT_CHANNEL_F"))
    
     
    # Natural Language Understanding - Natural Language Understanding-h3
    nlu_username = os.environ.get("NLU_USERNAME_1", os.getenv("NLU_USERNAME_F"))
    nlu_password = os.environ.get("NLU_PASSWORD_1", os.getenv("NLU_PASSWORD_F"))
    
    # Bluemix Object Storage - “Object Storage-01” 
    objstor_key = os.environ.get("OBJSTOR_KEY_1", os.getenv("OBJSTOR_KEY_F"))
    objstor_authurl = os.environ.get("OBJ_STOR_AUTHURL_1", os.getenv("OBJ_STOR_AUTHURL_F"))
    objstor_projectid = os.environ.get("OBJ_STOR_PROJECT_ID_1", os.getenv("OBJ_STOR_PROJECT_ID_F"))
    objstor_userid = os.environ.get("OBJ_STOR_USER_ID_1", os.getenv("OBJ_STOR_USER_ID_F"))
    objstor_region_name = os.environ.get("OBJ_STOR_REGION_NAME_1", os.getenv("OBJ_STOR_REGION_NAME_F"))
    
    # Cortical API Key 
    cortical_key = os.environ.get("CORTICAL_KEY_1", os.getenv("CORTICAL_KEY_F"))
        
    if not all((conversation_username, conversation_password, workspace_id, bot_id, slack_bot_token, nlu_username, nlu_password, cortical_key, gv_bot_deafault_channel_name)):
            # If some of the service env vars are not set get them from VCAP
            vcap_env = None
            conversation_creds = None
            vcap_services = os.environ.get("VCAP_SERVICES")
            if vcap_services:
                vcap_env = json.loads(vcap_services)
            if vcap_env:
                
                conversation_creds = get_vcap_credentials(vcap_env, 'conversation')
                conversation_username = conversation_username or conversation_creds['username']
                conversation_password = conversation_password or conversation_creds['password']

                nlu_creds = get_vcap_credentials(vcap_env, 'natural-language-understanding')
                nlu_username = nlu_username or nlu_creds['username']
                nlu_password = nlu_password or nlu_creds['password']

#                 bot_id = bot_id or conversation_creds['bot_id']
#                 bot_name = bot_name or conversation_creds['bot_name']
#                 slack_bot_token = slack_bot_token or conversation_creds['slack_bot_token']
#                 cortical_key = cortical_key or conversation_creds['cortical_key']
#                 gl_bot_deafault_channel_name = gv_bot_deafault_channel_name or conversation_creds['bot_deafault_channel']

            # If we still don't have all the above plus a few, then no WOS.
            if not all((conversation_username, conversation_password, workspace_id, bot_id, bot_name, slack_bot_token, nlu_username, nlu_password, cortical_key, gv_bot_deafault_channel_name)):
                print("Not all Environmental Variables are set")
                return None, None, None, None, None

    try:
        # Instantiate Cortical Client
        gv_cortical_client = retinasdk.FullClient(cortical_key, apiServer="http://api.cortical.io/rest", retinaName="en_associative")

        # Instantiate Watson Conversation client.
        conversation_client = ConversationV1(username=conversation_username, password=conversation_password, version='2016-09-20')
    
        gv_nlu = NaturalLanguageUnderstandingV1(username=nlu_username, password=nlu_password, version='2017-04-24')
    
        # instantiate Bluemix Object Storage
        gv_objstore_conn = swiftclient.Connection(key=objstor_key, authurl=objstor_authurl, auth_version='3',
                                              os_options={
                                                  "project_id": objstor_projectid,
                                                  "user_id": objstor_userid,
                                                  "region_name": objstor_region_name})
        # Instantiate Slack chatbot.
        slack_client = SlackClient(slack_bot_token)
    except:
        print("Connection to the Services could not be established !!!")
        return None, None, None, None, None    
         
            
    # If BOT_ID wasn't set, we can get it using SlackClient and user ID.
    if not bot_id:
        api_call = slack_client.api_call("users.list")
        if api_call.get('ok'):
            # retrieve all users so we can find our bot
            users = api_call.get('members')
            for user in users:
                if bot_name in user and user.get('name') == conversation_username:
                    bot_id = user.get('id')
                    print("Found BOT_ID=" + bot_id)
                else:
                    print("could not find user with the name " + conversation_username)
        else:
            print("could not find user because api_call did not return 'ok'")
            bot_id=None
                    
        if not bot_id:
            print("Error: Missing BOT_ID or invalid SLACK_BOT_USER.")
            return None, None, None, None, None
    # get Channel ID for the default Channel
    vChannels = slack_client.api_call("channels.list", exclude_archived=1)
    for x in vChannels['channels']:
        if x["name"] == gv_bot_deafault_channel_name:
            gv_bot_deafault_channel_id = x["id"]
        
       
#     LOG.debug("Connection estabilished with both, Watson Bot and Slack !!!" )
    return (workspace_id, bot_id, bot_name, conversation_client, slack_client)

def parse_slack_output(bot_id, bot_name, output_dict):
    """Prepare output when using Slack as UI.
       :param dict output_dict: text, channel, user, etc from slack posting
       :returns: text, channel, user
       :rtype: str, str, str"""
    
    at_bot_id = "<@" + bot_id + ">"
    at_bot_name = "@" + bot_name
    if output_dict and len(output_dict) > 0:
        for output in output_dict:
            if output and 'text' in output and 'user' in output and ('user_profile' not in output) and (output['user'] != "USLACKBOT") :
                if (at_bot_id in output['text']):
                    return (''.join(output['text'].split(at_bot_id)).strip(), output['channel'], output['user'])
                elif (at_bot_name in output['text']):
                    return (''.join(output['text'].split(at_bot_name)).strip(), output['channel'], output['user'])                    
                elif (output['channel'].startswith('D') and output['user'] != bot_id):
                    # Direct message!
                    return (output['text'].strip(), output['channel'], output['user'])
        return None, None, None

def get_urls(slack_client, message):  
    """extract URLs from teh message and store in the list. 
       :param slack_client - reference to the Slack object; message - text message
       :returns: list of the Urls or None if no URL found in the message
       :rtype: List """
    url_list = []
    vUrls = ""
    vUrl = ""
    vHasUrl = re.search("(?P<url>https?://[^\s]+)", message)    ## check if message has URL
    if vHasUrl is not None:
        message_list = [item for item in message.split(" ")]    ## create a list with the words from th emessage text 
        for item in message_list:
            vUrls = re.search("(?P<url>https?://[^\s]+)", item) ## extract URL from the text and store it in the search object 
            if vUrls is not None:
                url = vUrls.group("url")                        ## extract URL from teh search object   
                url = url[:url.rfind('|')]                      ## remove part of the URL starting from indicated symbol
                url = url.replace(">","")                             ## remove ">" from URL
                url = url.replace("amp;","")                          ## remove "anp;" from URL
                url_list.append(url)
        return url_list
    else:
        return None 

def convert_nlujson(url, nlu_response):
    """extracts features from NLU JSON outcome and stores in lists.
     Argument: NLU result - JSON format
     Return: 
    """
    response = ""
        
    try:
        nlu_sentiment = nlu_response['sentiment']["document"]["label"]
        response = "SENTIMENT: " + nlu_sentiment
    except KeyError:
        response = "SENTIMENT: not found"
     
    nlu_categoties = []
    response = response + "\n\nCATEGORIES: "
    try:
        for item in nlu_response['categories']:
            nlu_categoties.append(item['label'])
            response = response + item['label'] + ", "
    except KeyError:
        response = response + "not found."
            
    nlu_entities = []
    response = response + "\n\nCOMPANIES: "
    try:
        for item in nlu_response['entities']:
            if item["type"] == "Company":
                nlu_entities.append(item['text'])
                response = response + item['text'] + ", "
    except KeyError:
        response = response + "not found."
    
    nlu_keywords = []
    response = response + "\n\nKEYWORDS: "
    try: 
        for item in nlu_response['keywords']:
            if len(nlu_keywords) <= 10: 
                nlu_keywords.append(item['text'])
                response = response + item['text'] + ", "
            else:
                break
    except KeyError:
        response = response + "not found."
    
    nlu_concepts = []
    summarized_text = ""
    response = response + "\n\nCONCEPTS: "
    try:
        for item in nlu_response['concepts']:
            nlu_concepts.append(item['text'])
            response = response + item['text'] + ", "        
    except KeyError:
        response = response + "not found."
    
    try:
        nlu_analyzed_text = nlu_response['analyzed_text']
#         summarized_text = summarize.summarize_text(nlu_analyzed_text)
#         response = response + "\nSUMMARIZED TEXT: " + summarized_text.__str__()
#         summarized_text_url = summarize.summarize_page(url)                             ## uncoment to enable text summarization
#         response = response + "\n\nSUMMARIZED URL: " + summarized_text_url.__str__()    ## uncomment to add Summarized Text to the response 
#         response = response + "\n\nANALYZED TEXT: " + nlu_analyzed_text                 ## uncomment to add Analyzed Text to the response
    except KeyError:
        nlu_analyzed_text = ""
    
    try:
        nlu_metadata = nlu_response['metadata']
    except KeyError:
        nlu_metadata = ""
    try:
        nlu_relations = nlu_response['relations']          
    except KeyError:
        nlu_relations = ""
        
    return response, nlu_sentiment, nlu_categoties, nlu_entities, nlu_keywords, nlu_concepts, nlu_analyzed_text 

def get_categfilter_fprint(vFilterName, vReltext, vUnreltext):
    """ Create category filter for the related and unrelated text passed as an argument. 
    
    Argument: vFilterName - the name of the Category Filer; vReltext - related text;  vUnreltext - unrelated text 
    Return: Fingerprint of the Category Filter
    """   
    global gv_cortical_client, gv_objstore_conn
    
    cortical_categfilter_fprint = None
    vReltext_list = [""]
    vUnreltext_list = [""]
                  
    # Create a filter Fingerprint from positive (related) and negative (unrelated) example texts.
    if vReltext is not None:
        vReltext_list = list(filter(None, vReltext.strip().split(".")))               # converting related text into a list by breaking the text by sentences and removing the blank items form the list
        try:
            if vUnreltext is not None:          # use both Related and Unrelated filters
                vUnreltext_list = list(filter(None, vUnreltext.strip().split(".")))    # converting unrelated text into a list
                cortical_categfilter_fprint = gv_cortical_client.createCategoryFilter(vFilterName, vReltext_list, negativeExamples = vUnreltext_list)
            else:
                cortical_categfilter_fprint = gv_cortical_client.createCategoryFilter(vFilterName, vReltext)                
        except:
            print("Fingerprint can not be retrieved for " + vFilterName + " Category Filter")
            cortical_categfilter_fprint = None
    else:
        print("Category filter is not defined for " + vFilterName)
        cortical_categfilter_fprint = None
    return cortical_categfilter_fprint  

def get_technologies_fprint():
    """ Retrieves information from the Technology file "technologies_fprint.csv" into List and String. 
    Retrieves Fingerprints of the Technologies String 
    
    Argument: None
    Return: String of Technologies, Fingerprint of the String of Technologies
    """    
    global gv_cortical_client, gv_objstore_conn
    technologies_list = []
    technologies_string = None
    technologies_string_fprint = None
    objstore_file_object = None
    objstore_file_string = None
    technologies_df = None
    
    # download CSV file from Bluemix Object Storage 
    try:
        objstore_file_object = gv_objstore_conn.get_object(OBJSTOR_CONETEINER, FILE_TECHNOLOGIES)   # Open svc file from the Object Storage
        objstore_file_string = objstore_file_object[1].decode('utf-8')
        technologies_df=pd.read_csv(io.StringIO(objstore_file_string), sep=",")
    except:
        print("File " + FILE_TECHNOLOGIES + "not found or can not be opened")
        return None, None 
    
#     # to read CSV files from the local disk    
#     try:
#         technologies_df = pd.read_csv(FILE_TECHNOLOGIES)                                       # opens Technologies file
#     except:
#         print("File technologies.csv not found or can not be opened")
#         return None, None
    
    technologies_list = technologies_df["Technology"].tolist()                                  # reads column "Technology" and stores into List
    technologies_string = "".join(word +", " for word in technologies_list)                     # builds String of technologies from the List
    if technologies_string is not None:  
        try:
            technologies_string_fprint = gv_cortical_client.getFingerprintForText(technologies_string)  # gets fingerprints of Technologies String from CORTICAL.IO
        except:
            print("Fingerprint can not be retrieved for the Technologies")
            technologies_string_fprint = None
    else:
        print("Technologies can not be retrieved from the Technologies file")
        technologies_string_fprint = None
    return technologies_string, technologies_string_fprint 

def get_companies_fprint(nlu_entities):
    """ Retrieves information from the Companies file "COMPANIES.CSV into List and String. 
    Retrieves Fingerprints of the Companies String 
    
    Argument: None
    Return: String of Companies, Fingerprint of the String of Companies
    """    
    global gv_cortical_client, gv_objstore_conn
    
    companies_list = []
    companies_string = ""
    nlu_entities_string = ""
    nlu_entities_string_fprint = None
    companies_df = None
    companies_string_fprint = None
    objstore_file_object = None
    
    # download CSV file from Bluemix Object Storage 
    try:
        objstore_file_object = gv_objstore_conn.get_object(OBJSTOR_CONETEINER, FILE_COMPANIES)
        objstore_file_string = objstore_file_object[1].decode('utf-8')
        companies_df=pd.read_csv(io.StringIO(objstore_file_string), sep=",")
    except:
        print("File companies.csv not found or can not be opened")
        return None, None, None
        
    # to read CSV files from the local disk 
#     try:
#         companies_df = pd.read_csv(FILE_COMPANIES)                          # opens Technologies file
#     except:
#         print("File companies.csv not found or can not be opened")
#         return None, None, None
    
#     companies_list = list(set(companies_df["Company"]))                     # reads column "Company", converts into Set to remove duplicates and stores into list  === UNCOMENT TO REMOVE DUBLICATES
    companies_list = list(companies_df["Company"])                          # reads column "Company" and stores into list
    companies_string = "".join(word +", " for word in companies_list)       # builds String of Companies from the List
    if companies_string is not None:  
        try:
            companies_string_fprint  = gv_cortical_client.getFingerprintForText(companies_string)  # gets fingerprints of Technologies String from CORTICAL.IO
        except:
            print("Fingerprint can not be retrieved for the Companies")
            companies_string_fprint = None
    else:
        print("Companies can not be retrieved from the Companies file")
        companies_string_fprint = None

    # checks if Watson companies have been retrieve and builds a string. 
    if nlu_entities is not None:
        nlu_entities_string = "".join(word +", " for word in nlu_entities)   # builds String of Companies from the WATSON NLU Entities List
        try:
            nlu_entities_string_fprint = gv_cortical_client.getFingerprintForText(nlu_entities_string)  # gets fingerprints of Watson Entities (Companies) from CORTICAL.IO 
        except:
            print("Fingerprint can not be retrieved for the Companies extracted by Watson NLU")
            nlu_entities_string_fprint = None    
    else:
        nlu_entities_string = None

    return companies_string, companies_string_fprint, nlu_entities_string_fprint


def update_technologies_fprint():
    """updates technologies fingerprint from Cortical.ui 
    Looks to the technologies.csv file and updates Term and Text fingerprints for each technology
    Saves results in the new file technology_fprint.scv and overwrits any existing file with the same name. 
    
    Argument: None
    Return: None
    """ 
    global gv_cortical_client
            
    try:
        technologies_df = pd.read_csv(FILE_TECHNOLOGIES) 
    except:
        print("File technologies.csv can not be opened. Try to update Fingerprints later")
        return
    
    technologies_df["TermFprint"] = None
    technologies_df["TextFprint"] = None
        
    for index, row in technologies_df.iterrows():
        vFprintTerm = row["TermFprint"]
        vFprintText = row["TextFprint"]  
        vTechnology_str = row["Technology"] 
        vNumbofWords = len(vTechnology_str.split())
        print(str(row["ID"]) + " - " + str(row["Technology"]))
        try:
            vFprintTerm = gv_cortical_client.getTerms(vTechnology_str.encode('utf-8'), getFingerprint = True) 
        except:
            vFprintTerm = None
            
        if not vFprintTerm:
            technologies_df["TermFprint"][index] = None
        else:
            technologies_df["TermFprint"][index] = vFprintTerm[0].fingerprint.positions.__str__()
            
        try:
            vFprintText = gv_cortical_client.getFingerprintForText(vTechnology_str.encode('utf-8'))
        except:
            vFprintText = None
            
        if not vFprintText:
            technologies_df["TextFprint"][index] = None
        else:
            technologies_df["TextFprint"][index] = vFprintText.positions.__str__()   
    
    technologies_df.to_csv(FILE_TECHNOLOGIES_FPRINT)
    print("Fingerprints updated for Terms and Texts of each technology, check file technologies_fprint.csv" )
    return None

def rank_technologies(nlu_analyzed_text,nlu_analyzed_text_fprint):
    """updates technologies fingerprint from Cortical.ui 
    Looks to the technologies.csv file and updates Term and Text fingerprints for each technology
    Saves results in the new file technology_fprint.scv and overwrits any existing file with the same name. 
    
    Argument: None
    Return: None
    """ 
    global gv_cortical_client
    
    vCompMessage = ""
    vCompareRresults = None
    
    # download CSV file from Bluemix Object Storage 
    try:
        objstore_file_object = gv_objstore_conn.get_object(OBJSTOR_CONETEINER, FILE_TECHNOLOGIES_FPRINT)
        objstore_file_string = objstore_file_object[1].decode('utf-8')
        technologies_df=pd.read_csv(io.StringIO(objstore_file_string), sep=",")
    except:
        print("Technologies Fingerprint file: " + FILE_TECHNOLOGIES_FPRINT + " can not be opened !!!")
        return False       
    
#     try:
#         technologies_df = pd.read_csv(FILE_TECHNOLOGIES_FPRINT) 
#     except:
#         print("File :" + FILE_TECHNOLOGIES_FPRINT + " can not be opened !!!")
#         return
    
    technologies_df["Rank"] = 0.0
    
        
    for index, row in technologies_df.iterrows():
        vFprintTerm = row["TermFprint"]
        vFprintText = row["TextFprint"]
        vTechnology_str = row["Technology"]

        # check if Technology is a term or text and perform comparison accordingly 
        if pd.notnull(vFprintTerm): 
            # Compare Term (siingle word Technology with the analyzed test) 
            vCompareRresults = gv_cortical_client.compare(json.dumps([{"term": vTechnology_str}, {"text": nlu_analyzed_text}]))
            print(str(index) + " - " + vTechnology_str+": " + str(vCompareRresults.cosineSimilarity)) 
            technologies_df["Rank"][index] = vCompareRresults.cosineSimilarity
        else:           # if technology is not a term (if it has more than one word, check if there is a text fingerprint
            if pd.notnull(vFprintText):
                vCompareRresults = gv_cortical_client.compare(json.dumps([{"text": vTechnology_str}, {"text": nlu_analyzed_text}]))
                print(str(index)  + " - " + vTechnology_str+": " + str(vCompareRresults.cosineSimilarity))
                technologies_df["Rank"][index] = vCompareRresults.cosineSimilarity
            else:
                print(vTechnology_str + ": NO FINGERPRINT FOUND FOR THE TECHNOLOGY TEXT !!!")
                technologies_df["Rank"][index] = 0
    
    technologies_df.to_csv(FILE_TECHNOLOGIES_RANK)
    print("ranking of the Technologie has been completed, check file: " + FILE_TECHNOLOGIES_RANK )
    return True

def get_categfilters_list():
    """reds Category Filters List file fileters_list.csv from the Bluemix and 
    stored in the Data Frame. the file stores a list fo all possible Category Filters 
    and corresponding CSV files 
    
    Argument: None
    Return: Data Frame with the Names of the filters and corresponding Files. 
    """ 
    
    global gv_objstore_conn
    
    objstore_file_object = None
    objstore_file_string = None
    filters_list_df = None
    
    # download CSV file from Bluemix Object Storage 
    try:
        objstore_file_object = gv_objstore_conn.get_object(OBJSTOR_CONETEINER, FILE_FILTERS_LIST)
        objstore_file_string = objstore_file_object[1].decode('utf-8')
        filters_list_df=pd.read_csv(io.StringIO(objstore_file_string), sep=",")
    except:
        print("File " + FILE_FILTERS_LIST +" not found or can not be opened")
        return None


    # to read CSV files from the local disk 
#     try:
#         filters_list_df = pd.read_csv(FILE_FILTERS_LIST)                          
#     except:
#         print("File " + FILE_FILTERS_LIST +" not found or can not be opened")
#         return None
            
    return filters_list_df  


    

def cortical_analyze(nlu_analyzed_text, nlu_keyword, nlu_entities):
    global gv_cortical_client
    
    cortical_responce_text = ""
    cortical_keywords_list = []
    cortical_keywords_string = ""
    cortical_companies_string = "" 
    cortical_companies_string_fprint = None
    nlu_keywords_list_fprint = None 
    nlu_entities_string_fprint = None
    nlu_keywords_string = ""
    companies_compare = None
    cortical_categfilter_fprint = None
    filters_list_df = None
    vFilterName = None
    vFilename = None 

    nlu_analyzed_text_encoded = nlu_analyzed_text.encode('utf-8')
#     nlu_analyzed_text_encoded = nlu_analyzed_text.replace("\n"," ")
#     nlu_analyzed_text_encoded = re.sub(r'[^\w]', ' ', nlu_analyzed_text_encoded).encode('utf-8')
    
       
    
    # if Watson was not able to extract Keywords form the text, then get keywords from Cortical.IO
    if nlu_keyword is None:
        try:
            cortical_keywords_list = gv_cortical_client.getKeywordsForText(nlu_analyzed_text_encoded)   # gets Keywords from Analyzed Text and stores in the List
            cortical_keywords_string = "".join(word +", " for word in cortical_keywords_list)           # builds String from Keywords List
            cortical_responce_text = "\n\nCORTICAL KEYWORDS: " + cortical_keywords_string               # updates response text
        except:
            cortical_responce_text = "\n\nCORTICAL KEYWORDS: can not be extracted" 

    # Get Fingerprint of the Analyzed Text from CORCTICAL
    try:
        nlu_analyzed_text_fprint = gv_cortical_client.getFingerprintForText(nlu_analyzed_text_encoded)
    except:
        return "\n\nSemantic analysis can not be performed. Not able to retrieve Fingerprints of the Text"  


    #***************************Uncomment to rank technologies. takes some time ***********************************************
#    rank_technologies(nlu_analyzed_text,nlu_analyzed_text_fprint)
    
    cortical_responce_text = cortical_responce_text + "\n\n\n ===== Semantic Analysis ====="  
    # Retrieves TECHNOLOGIES Fingerprints and compares ANALYZED TEXT's and TECHNOLOGIES STRING Fingerprint. Updates response text with the result of comparison           
    technologies_string, technologies_string_fprint  = get_technologies_fprint()
    if all((technologies_string, technologies_string_fprint)):
        technologies_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_analyzed_text_fprint.positions}, {"positions": technologies_string_fprint.positions}]))
        cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT AND TECHNOLOGIES:\nSimilarity: " + str(technologies_compare.cosineSimilarity)
            
#         # compares ANALYZED TEXT and TECHNOLOGIES String. Updates response text with the result of comparison  -- UNCOMENT TO ADD TECHNOLOGY STRING and Text comparison           
#         technologies_compare = gv_cortical_client.compare(json.dumps([{"text": nlu_analyzed_text}, {"text": technologies_string}]))
#         cortical_responce_text = cortical_responce_text + "\n\nSEMANTIC COMPARISON OF THE TEXT AND TECHNOLOGIES TEXT:\nSimilarity: " + str(technologies_compare.cosineSimilarity)         
        
        # if Watson extracted Keywords form the text
        if nlu_keyword is not None:
            # Get Fingerprint of the list of WATSON KEYWORDS from CORCTICAL
            nlu_keywords_string = "".join(word +", " for word in nlu_keyword)           # builds String from Keywords List
            nlu_keywords_list_fprint = gv_cortical_client.getFingerprintForText(nlu_keywords_string.encode('utf-8')) 
            
            # Compares WATSON KEYWORDS and TECHNOLOGIES STRING. Updates response text with the result of comparison
            technologies_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_keywords_list_fprint.positions}, {"positions": technologies_string_fprint.positions}]))
            cortical_responce_text = cortical_responce_text + "\n\nComparison of the WATSON KEYWORDS and TECHNOLOGIES:\nSimilarity: " + str(technologies_compare.cosineSimilarity)
                                                                                                                        
        else:  
            if cortical_keywords_string is not None:
                # Compares CORTICAL KEYWORDS and TECHNOLOGIES STRING. Updates response text with the result of comparison 
                technologies_compare = gv_cortical_client.compare(json.dumps([{"text": cortical_keywords_string}, {"text": technologies_string}]))
                cortical_responce_text = cortical_responce_text + "\n\nComparison of the CORTICAL KEYWORDS and TECHNOLOGIES:\nSimilarity: " + str(technologies_compare.cosineSimilarity)
            else:
                cortical_responce_text = cortical_responce_text + "\n\nComparison of the CORTICAL KEYWORDS and TECHNOLOGIES: not performed"     
    else:
        cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and TECHNOLOGIES: not performed"
 
    # COMPANIES - gets Fingerprints for the string of Companies from the COMPANIES file. 
    cortical_companies_string, cortical_companies_string_fprint, nlu_entities_string_fprint = get_companies_fprint(nlu_entities)
    if nlu_entities_string_fprint is not None:                      ## if Companies have been extracted by Watson, then compare fingerprints of Watson Companies and Companies from the file. 
        # Compare Fingerprints of the Strings of Watson Entities (Companies) and Companies (from the Companies File). Update response text with the results 
        companies_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_entities_string_fprint.positions}, {"positions": cortical_companies_string_fprint.positions}]))
        cortical_responce_text = cortical_responce_text + "\n\nComparison of the WATSON COMPANIES and COMPANIES LIST:\nSimilarity: " + str(companies_compare.cosineSimilarity)
    else:                                                           ## if Companies have not been extracted by Watson, then compare fingerprints of the Analyzed Text and Companies from the file 
        if cortical_companies_string_fprint is not None:
            # Compare Fingerprints of the Analyzed Text and Companies String and update response text with the results 
            companies_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_analyzed_text_fprint.positions}, {"positions": cortical_companies_string_fprint.positions}]))
            cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and COMPANIES LIST:\nSimilarity: " + str(companies_compare.cosineSimilarity)
        else:
            cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and WATSON COMPANIES: not performed"   
             
    
    # CATEGORY FILTERS - Comparison of the text and Category Filters fingerprints
    filters_list_df = get_categfilters_list()                                                                               # get list of filters from Bluemix into DataFrame
    if filters_list_df is not None:
        cortical_responce_text = cortical_responce_text + "\n\n\n ===== Category Filters and Text ====="  
        for index, row in filters_list_df.iterrows():                                                                       # read rows from the Data Frame with the Category Filters 
            vFilterName = row["FilterName"]
            vFilename = row["FileName"]  
            vReltext = row["Related"]
            vUnreltext = row["Unrelated"]
            
            # Check if filter is active and get fingerprints and conduct comparison 
            if row["Active"] == "yes" and vFilterName is not None:
                # get fingerprint of each active category filter of the List
                cortical_categfilter_fprint = get_categfilter_fprint(vFilterName, vReltext, vUnreltext)
                if cortical_categfilter_fprint is not None:
                    # Compare Fingerprints of the Analyzed Text and Category Filters and update response text with the results 
                    categfilters_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_analyzed_text_fprint.positions}, {"positions": cortical_categfilter_fprint.positions}]))            
                    cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and " + vFilterName + ":\nSimilarity: " + str(categfilters_compare.cosineSimilarity)
                else:
                    cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and " + vFilterName + ": not performed"

        cortical_responce_text = cortical_responce_text + "\n\n\n ===== Category Filters and KEYWORDS ====="  
        for index, row in filters_list_df.iterrows():                                                                       # read rows from the Data Frame with the Category Filters 
            vFilterName = row["FilterName"]
            vFilename = row["FileName"]  
            vReltext = row["Related"]
            vUnreltext = row["Unrelated"]
            
            # Check if filter is active and get fingerprints and conduct comparison 
            if row["Active"] == "yes" and vFilterName is not None:
                # get fingerprint of each active category filter of the List
                cortical_categfilter_fprint = get_categfilter_fprint(vFilterName, vReltext, vUnreltext)
                if cortical_categfilter_fprint is not None:
                    # Compare Fingerprints of the Analyzed Text and Category Filters and update response text with the results 
                    categfilters_compare = gv_cortical_client.compare(json.dumps([{"positions": nlu_keywords_list_fprint.positions}, {"positions": cortical_categfilter_fprint.positions}]))            
                    cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and " + vFilterName + ":\nSimilarity: " + str(categfilters_compare.cosineSimilarity)
                else:
                    cortical_responce_text = cortical_responce_text + "\n\nComparison of the TEXT and " + vFilterName + ": not performed"


        
    return cortical_responce_text


def handle_message(conversation_client, slack_client, workspace_id, context, message, channel, user):
    """Handler for messages coming from Watson Conversation using context.

        Fields in context will trigger various actions in this application.

        :param str message: text from UI
        :param SlackSender sender: used for send_message, hard-coded as Slack

        :returns: True if UI input is required, False if we want app
         processing and no input
        :rtype: Bool
    """
    global gv_nlu, gv_cortical_client, gv_bot_deafault_channel_name, gv_bot_deafault_channel_id 
    url_list = []      
    response = ""
    cortical_response_text = ""
    nlu_analyzed_text = ""
    nlu_responce_text = ""
    nlu_keyword = None
    nlu_entities = None
    context = None

    # extract URLs from the message of the post 
    url_list = get_urls(slack_client, message) 
    
    if url_list is not None: 
        # send the message to user indicating that teh process of analysis started 
        slack_client.api_call("chat.postMessage", channel=channel, text="analyzing . . . ", as_user=True)
        for i in range(len(url_list)):                                                
            try:
                # Analyze the URL article using WATSON Natural Language Understanding
                nlu_response = gv_nlu.analyze(url=url_list[i], return_analyzed_text=True, features=[features.Categories(), features.Concepts(), features.Emotion(), features.Entities(), 
                                                                                                features.Keywords(), features.MetaData(), features.Relations(), features.Sentiment() ])
                # get information from JSON format resulted by NLU 
                nlu_responce_text, nlu_sentiment, nlu_categoties, nlu_entities, nlu_keyword, nlu_concepts, nlu_analyzed_text  = convert_nlujson(url_list[i], nlu_response)

            except WatsonException:
                # print(json.dumps(nlu_response, indent=2))
                nlu_responce_text = "Sentiments can not be retrieved from the URL"
            
            # performs CORTICAL SEMANTIC analysis and returns results as a response text 
            cortical_response_text = cortical_analyze(nlu_analyzed_text, nlu_keyword, nlu_entities)
                        
            # build response text
            title = "\n\n\n ===== Watson Sentiment Analysis =====\n"  
            response = url_list[i] + title + nlu_responce_text + cortical_response_text 
            
#             slack_client.api_call("chat.postMessage", channel=gv_bot_deafault_channel_id, text=response, as_user=True)  ## uncomment to post responses at Default channel
            slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)                     ## uncomment to post responses at the sender's channel
            i=i+1
    
    # post receipt of the messate on the channel if it is not recevied from the default channel              
#     if channel != gv_bot_deafault_channel_id :                                                                    ## uncomment to send receipt of the url to the sender
#         slack_client.api_call("chat.postMessage", channel=channel, text="Thanks, new post has been received !!!", as_user=True)
            
    else:
        slack_client.api_call("chat.postMessage", channel=channel, text="No URL found!!!. \nI am trained to read text from URL, conduct sentiment analysis and classify it using semantic comparison with points of interests: Technologies, Companies and Interests", as_user=True)

    
    return True
    
    ###### WATSON CONVERSTATION: Pass message to Watson Conversation and get a response                        
#     watson_response = conversation_client.message(workspace_id=workspace_id, message_input={'text': message}, context = context)   
#     if 'context' in watson_response:
#         context = watson_response['context'] 
#     response = ''
#     for text in watson_response['output']['text']:
#         response += text + "\n"
#     slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)
#     print("Watson: ", text)
#     return True
#
#         if ('discovery_string' in self.context.keys() and
#            self.context['discovery_string'] and self.discovery_client):
#             return self.handle_discovery_query()
# 
#         if ('shopping_cart' in self.context.keys() and
#                 self.context['shopping_cart'] == 'list'):
#             return self.handle_list_shopping_cart()
# 
#         if ('shopping_cart' in self.context.keys() and
#                 self.context['shopping_cart'] == 'add' and
#             'cart_item' in self.context.keys() and
#                 self.context['cart_item'] != ''):
#             return self.handle_add_to_cart()
# 
#         if ('shopping_cart' in self.context.keys() and
#                 self.context['shopping_cart'] == 'delete' and
#             'cart_item' in self.context.keys() and
#                 self.context['cart_item'] != ''):
#             return self.handle_delete_from_cart()
# 
#         if ('get_input' in context.keys() and
#                 context['get_input'] == 'no'):
#                 return False    


def main():
    
    user_input = '' 
    update_fingerprints = False
    context = {}
    workspace_id, bot_id, bot_name, conversation_client, slack_client = init_connections()
    slack_output = None
    
    # set update_fingerprints to True to update fingerprint for the list of technologies
    if update_fingerprints is True:
        update_technologies_fprint()
     
    if slack_client.rtm_connect():
        # LOG.info("Slack bot is connected and running!")
        while True: 
            slack_output = slack_client.rtm_read()           
            if slack_output:
                # LOG.debug("slack output\n:{}\n".format(slack_output))
                print(slack_output)
                message, channel, user = parse_slack_output(bot_id, bot_name, slack_output)
                print("Slack: ", message)
                if message and channel and message != None and channel != None:
                    get_input = handle_message(conversation_client, slack_client, workspace_id, context, message, channel, user)
                    while not get_input:
                        get_input = handle_message(conversation_client, slack_client, workspace_id, context, message, channel, user)
 
            time.sleep(0.5)
    else:
        # LOG.warning("Connection failed. Invalid Slack token or bot ID")
        print("Connection failed. Invalid Slack token or Bot ID")
            

if __name__ == "__main__":
    cf_deployment_tracker.track()
    main()

