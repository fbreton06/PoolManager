class MyClass:
    def alert(self, message):
        self.ACCOUNT_SID = "AC7a452e3f660c7759a73f2b5a4026790c"
        self.ACCOUNT_AUTH = "8391d2739f07a344d4b246aa853e03ef"
        self.ACCOUNT_PHONE_NUMBER = "+33756796236"
        # Creation d'un compte trial sur: https://www.twilio.com/sms
        # pip install twilio (need to install: sudo apt-get install build-essential libssl-dev libffi-dev python-dev)
        try:
            unused = self.sms
        except:
            # TurnAround: Non present pendant l'appel via /etc/rc.local
            from twilio.rest import Client as SMS
            self.sms = SMS(self.ACCOUNT_SID, self.ACCOUNT_AUTH)
        # TODO 2 lire les numero apartir de la database et donc les configurer a partir du web
        # faire 2 liste une pour les urgence avec tous le monde et une de surveillance
        phoneNumbers = ("0643648483",)# "0664983069", "0769493546", "0767069137"
        for number in phoneNumbers:
            self.sms.messages.create(from_=self.ACCOUNT_PHONE_NUMBER, to="+33"+number[-9:], body=message)
