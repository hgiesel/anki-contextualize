import urllib
import json
import re
import pprint

class AnkiConnection:
    def __init__(self, card_config, card_sets, port=8765, printer=print):
        '''setup connection to anki'''
        self.req = urllib.request.Request('http://localhost:' + str(port))
        self.req.add_header('Content-Type', 'application/json; charset=utf-8')
        self.card_config = card_config
        self.card_sets = card_sets
        self.printer = printer

        try:
            add_resp = urllib.request.urlopen(self.req)
        except:
            self.printer('connection to db cannot be established')

    def anki_add(self, tag, qid=None, content=None, option=0):
        card_sets_option = self.card_sets[option]

        tag_pref = (self.card_config['pageid_prefix'] + '::' if self.card_config['pageid_prefix'] else '')
        tag_suff = ('::' + self.card_config['pageid_suffix'] if self.card_config['pageid_suffix'] else '')

        tag_full = tag_pref + tag + tag_suff

        add_req = json.dumps({
                'action': 'guiAddCards',
                'version': 6,
                'params': {
                    'note': {
                        'deckName': (self.card_config['deck_name']
                                     if not card_sets_option['deck_subdeck']
                                     else '%s::%s' % (self.card_config['deck_name'], card_sets_option['deck_subdeck'])),
                        'modelName': card_sets_option['model_name'],
                        'fields': {
                            self.card_config['qid_field']: (qid if qid and not self.card_config['qid_use_prefill'] else ''),
                            card_sets_option['content_field']: (content.strip().replace('\n','<br />') if content else '')
                            },
                        'options': {
                            'closeAfterAdding': True
                            },
                        'tags': [
                            tag_full
                            ]
                        }
                    }
                }).encode('utf-8')

        add_resp = urllib.request.urlopen(self.req, add_req)
        add_json = json.loads(add_resp.read().decode('utf-8'))
        return add_json

    def anki_browse(self, query, option=0):
        card_sets_option = self.card_sets[option]
        deck_name = (self.card_config['deck_name']
                     if not card_sets_option['deck_subdeck']
                     else '%s::%s' % (self.card_config['deck_name'], card_sets_option['deck_subdeck']))
        browse_query = ' '.join(query) + ' deck:{0}*'.format(deck_name)

        browse_req = json.dumps({
            'action': 'guiBrowse',
            'version': 6,
            'params': {
                'query': browse_query
                }
            }).encode('utf-8')

        browse_resp = urllib.request.urlopen(self.req, browse_req)
        browse_json = json.loads(browse_resp.read().decode('utf-8'))

        return browse_json


    def anki_query_check_against(self, resps, check_against, option=0):
        card_sets_option = self.card_sets[option]
        deck_name = (self.card_config['deck_name']
                     if not card_sets_option['deck_subdeck']
                     else '%s::%s' % (self.card_config['deck_name'], card_sets_option['deck_subdeck']))

        check_against_query = ' '.join(check_against) + ' deck:{0}*'.format(deck_name)

        check_against_req = json.dumps({
            'action': 'findNotes',
            'version': 6,
            'params': {
                'query': check_against_query
                }
            }).encode('utf-8')


        check_against_resp = urllib.request.urlopen(self.req, check_against_req)
        check_against_json = json.loads(check_against_resp.read().decode('utf-8'))

        check_against_filtered = [entry for entry in check_against_json['result'] if not entry in resps]

        if len(check_against_filtered):
            outsider_info_query = json.dumps({
            "action": "notesInfo",
            "version": 6,
            "params": {
                "notes": check_against_filtered
                }
            }).encode('utf-8')

            outsider_info_resp = urllib.request.urlopen(self.req, outsider_info_query)
            outsider_info_json = json.loads(outsider_info_resp.read().decode('utf-8'))

            tags = [list(filter(lambda tag: re.match('.*::.*', tag), entry['tags']))
                    for entry in outsider_info_json['result']]

            displayed_tags = [ ':'.join(re.match('(.*)::(.*)', ts[0]).groups()) if len(ts) == 1 else '???:???' for ts in tags]

            if self.card_config['qid_field']:
                quest_fields = [entry['fields'][self.card_config['qid_field']]['value'] for entry in outsider_info_json['result']]
                qid_regex = re.compile(r'^:?([0-9]+):?')
                quest_ids = [re.sub(r'(?:<[^>]*>)*?%s.*' % (qid_regex), r'\g<1>', entry) for entry in quest_fields]

            else:
                quest_ids = [entry['noteId'] for entry in outsider_info_json['result']]


            zipped_ids = list(zip(displayed_tags, quest_ids))
            zipped_ids_unique = set(zipped_ids)

            result = [i + (-zipped_ids.count(i),) for i in zipped_ids_unique]

            return result

        else:
            return []

    def anki_query_count(self, query_list, check_against=None, option=0):
        card_sets_option = self.card_sets[option]
        deck_name = (self.card_config['deck_name']
                     if not card_sets_option['deck_subdeck']
                     else '%s::%s' % (self.card_config['deck_name'], card_sets_option['deck_subdeck']))

        queries = [{
            'action': 'findNotes',
            'params': {'query': '%s deck:%s*' % (q, deck_name)}
            } for q in query_list]

        query = json.dumps({
            'action': 'multi',
            'version': 6,
            'params': {
                'actions': queries
                }
            }).encode('utf-8')

        resp = urllib.request.urlopen(self.req, query)
        resp_json = json.loads(resp.read().decode('utf-8'))

        counts = None
        if not None in resp_json['result']:
            counts = [len(r) for r in resp_json['result']]

        outsiders = []
        if check_against is not None:
            resp_flattened = [item for sublist in resp_json['result'] for item in sublist]
            outsiders = self.anki_query_check_against(resp_flattened, check_against, option=option)

        return (counts, outsiders)
