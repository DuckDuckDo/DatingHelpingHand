from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
import time
import json
import os
from shutil import copyfile
import platform


class Config:
    def __init__(self, target=None, file_path="config.json"):
        self.file_path = file_path

        # check if config exists, else create it from template
        if not os.path.isfile("config.json"):
            copyfile("config_template.json", "config.json")

        with open(file_path) as json_file:
            self.value = json.load(json_file)

        if target:
            path = target.split(".")
            for part in path:
                self.value = self.value[part]


class Secret:
    def __init__(self, target=None, file_path="secrets.json"):
        self.file_path = file_path

        # check if config exists, else create it from template
        if not os.path.isfile("secrets.json"):
            copyfile("secrets_template.json", "secrets.json")

        with open(file_path) as json_file:
            self.value = json.load(json_file)

        if target:
            path = target.split(".")
            for part in path:
                self.value = self.value[part]


class Log:
    def __init__(self, file_path="log.json"):
        self.file_path = file_path

        # check if config exists, else create it from template
        if not os.path.isfile("log.json"):
            copyfile("log_template.json", "log.json")

        with open(file_path) as json_file:
            self.value = json.load(json_file)

    def update(self, new_json):
        self.value = new_json
        with open("log.json", "w") as outfile:
            json.dump(self.value, outfile)


class WebDriver:
    def __init__(self):
        self.path = 'webdriver/'+platform.system()+'/geckodriver'


class Website:
    def __init__(
        self,
        headless=True,
        username=Secret("username").value,
        password=Secret("password").value,
        webdriver_path=WebDriver().path,
        age_max=Config("age_max").value,
        weight_max_kg=Config("weight_max_kg").value,
        min_price_eur=Config("my_eur_rate_per_hour_absolute_min").value,
    ):
        print("-> __init__()")
        self.username = username
        self.password = password
        self.headless = headless
        self.webdriver_path = webdriver_path
        self.limits = {
            "age_max": age_max,
            "weight_max_kg": weight_max_kg,
            "min_price_eur": min_price_eur,
        }
        self.windows = []
        self.log = Log()

        # start tab and login
        if self.username and self.password:
            self.new_window()
        else:
            print("-> ERROR: no username and password defined")

    def update_log(self):
        self.log.update(self.log.value)

    def close(self):
        print("-> close()")
        for window in self.windows:
            window.close()

    def new_window(self, url=None):
        print("-> new_window()")
        options = webdriver.FirefoxOptions()
        if self.headless:
            options.add_argument("-headless")
        window = webdriver.Firefox(
            executable_path=r"{}".format(self.webdriver_path), firefox_options=options
        )
        self.windows.append(window)

        latest_window = len(self.windows) - 1

        self.windows[latest_window].set_window_position(0, 0)
        self.windows[latest_window].set_window_size(1920, 1040)

        self.windows[latest_window].get("https://www.hunqz.com/auth/login")
        time.sleep(5)
        self.windows[latest_window].find_element_by_id("id_username").send_keys(
            self.username
        )
        self.windows[latest_window].find_element_by_id("id_password").send_keys(
            self.password
        )
        self.windows[latest_window].find_element_by_css_selector(
            "button.ui-button"
        ).click()
        time.sleep(5)

        if url:
            self.windows[latest_window].get(url)
            time.sleep(4)

    def conversations(self, new_only=True):
        print("-> conversations()")
        # go to the message section
        self.windows[0].get("https://www.hunqz.com/messenger/chat")
        time.sleep(8)

        # scroll down to load more messages
        act = ActionChains(self.windows[0])
        act.move_to_element(
            self.windows[0].find_element_by_class_name("refreshable")
        ).click()
        for i in range(0, 15):
            act.send_keys(Keys.PAGE_DOWN).perform()

        # find all conversations
        conversations = [
            x
            for x in self.windows[0].find_elements_by_class_name("listitem")
            if x.find_elements_by_tag_name("a")
            and not "hunq/HUNQZ-PLUS"
            in x.find_element_by_tag_name("a").get_attribute("href")
            and not x.find_elements_by_class_name("icon-chat-sent")
        ]

        if new_only:
            conversations = [
                x
                for x in conversations
                if x.find_elements_by_class_name("txt-pill--mini")
            ]

        return conversations

    def check_profile__for_compatibility(self, conversation):
        print("-> check_profile__for_compatibility()")
        url = conversation.find_element_by_tag_name("a").get_attribute("href")
        if len(self.windows) == 1:
            self.new_window(url)
        else:
            self.windows[1].get(url)
            time.sleep(5)
        time.sleep(5)

        # get the age
        age = (
            int(self.windows[1].find_elements_by_class_name("typo-figure")[0].text)
            if self.windows[1].find_elements_by_class_name("typo-figure")
            else None
        )

        # go over all the profile stats and if headline is weight, take weight
        profile_stats = self.windows[1].find_elements_by_class_name(
            "profile-stats__item.js-profile-stat"
        )
        for stat in profile_stats:
            if (
                stat.find_element_by_class_name("profile-stats__item-key").text
                == "Weight"
            ):
                weight = int(
                    stat.find_element_by_class_name(
                        "profile-stats__item-val"
                    ).text.replace("kg", "")
                )
                break
        else:
            weight = None

        # add profile to summary
        self.log.value["min_age"] = (
            age
            if not self.log.value["min_age"]
            or (age and self.log.value["min_age"] > age)
            else self.log.value["min_age"]
        )
        self.log.value["max_age"] = (
            age
            if not self.log.value["max_age"]
            or (age and self.log.value["max_age"] < age)
            and age < 90
            else self.log.value["max_age"]
        )
        self.log.value["min_weight"] = (
            weight
            if not self.log.value["min_weight"]
            or (weight and self.log.value["min_weight"] > weight)
            else self.log.value["min_weight"]
        )
        self.log.value["max_weight"] = (
            weight
            if not self.log.value["max_weight"]
            or (weight and self.log.value["max_weight"] < weight)
            else self.log.value["max_weight"]
        )
        str_age = str(age)
        str_weight = str(weight)
        if str_age in self.log.value["range_age"]:
            self.log.value["range_age"][str_age] += 1
        else:
            self.log.value["range_age"][str_age] = 1
        if str_weight in self.log.value["range_weight"]:
            self.log.value["range_weight"][str_weight] += 1
        else:
            self.log.value["range_weight"][str_weight] = 1

        self.update_log()

        # check if profile is within limits
        if (not age or age <= self.limits["age_max"]) and (
            not weight or weight <= self.limits["weight_max_kg"]
        ):
            return True
        else:
            return False

    def check_message__quick_share_request(self, conversation):
        print("-> check_message__quick_share_request()")
        new_message = conversation.find_element_by_class_name("js-preview-text").text
        return True if new_message == "Can I see your QuickShare photos?" else False

    def check_message__asks_for_too_low_price(self, conversation):
        print("-> check_message__asks_for_too_low_price()")
        # TODO
        # examples: 90eur, 90 eur, 90€, €90, 90 €,
        # examples: is 90 also fine?, 90, I give you 90
        new_message = conversation.find_element_by_class_name("js-preview-text").text
        prices_in_message = []
        prices_under_minimum = [
            x for x in prices_in_message if x < self.limits["min_price_eur"]
        ]
        return True if prices_under_minimum else False

    def check_message__simple_hey(self, conversation):
        print("-> check_message__simple_hey()")
        new_message = conversation.find_element_by_class_name("js-preview-text").text
        if len(new_message) < 8 and (
            "hey" in new_message
            or "hi" in new_message
            or "hallo" in new_message
            or "hello" in new_message
        ):
            return True
        else:
            return False

    def approve__quick_share_request(self, conversation):
        print("-> approve__quick_share_request()")
        conversation.find_elements_by_tag_name("a")[1].click()
        time.sleep(4)
        if self.windows[0].find_elements_by_class_name("js-grant-access"):
            self.windows[0].find_element_by_class_name("js-grant-access").click()
            self.log.value["approved_quick_share_requests"] += 1
            self.update_log()
            print(
                "Approved quick share request ({} total)".format(
                    self.log.value["approved_quick_share_requests"]
                )
            )

    def delete__conversation(self, conversation):
        print("-> delete__conversation()")
        conversation.find_elements_by_tag_name("a")[1].click()
        time.sleep(4)

        # press the delete button in the top right corner
        self.windows[0].find_element_by_css_selector(
            ".bonlkz-0 > button:nth-child(1)"
        ).click()
        time.sleep(1)

        # press delete in the popup overlay
        self.windows[0].find_element_by_css_selector(
            "button.Box-sc-3wxjho-0:nth-child(2)"
        ).click()

        self.log.value["deleted_conversations"] += 1
        self.update_log()
        print(
            "Deleted conversation ({} total)".format(
                self.log.value["deleted_conversations"]
            )
        )

    def reply(self, conversation, text):
        print("-> reply()")
        conversation.find_elements_by_tag_name("a")[1].click()
        time.sleep(4)
        self.windows[0].find_element_by_class_name("js-text").send_keys(text)
        self.windows[0].find_element_by_css_selector(".icon-send-message").click()

    def check_conversations(self):
        print("-> check_conversations()")
        conversations = self.conversations()
        print("->> process {} new conversations".format(len(conversations)))
        for conversation in conversations:
            # detect what to do with conversation

            # if person outside of limits: delete conversation
            if self.check_profile__for_compatibility(conversation) == False:
                self.delete__conversation(conversation)
                self.log.value["saved_time_minutes"] += 0.5
                self.update_log()

            # else if person asks for quickshare images: open conversation and press share
            elif self.check_message__quick_share_request(conversation) == True:
                self.approve__quick_share_request(conversation)
                self.log.value["saved_time_minutes"] += 0.5
                self.update_log()

            # else if person asks for stupidly low price: mention minimum price and delete conversation
            # elif self.check_message__asks_for_too_low_price(conversation) == True:
            #     #TODO
            #     self.reply(
            #         conversation,
            #         "my rate is {} per hour".format(
            #             Config("my_eur_rate_per_hour").value
            #         ),
            #     )
            #     self.delete__conversation(conversation)
            #     self.log.value["saved_time_minutes"] += 0.5
            #     self.update_log()

            # else if person just messages a short hey/hi (less then 15 char): auto reply with "Hey:) interested in a date?"
            elif self.check_message__simple_hey(conversation) == True:
                self.reply(conversation, "Hey:) interested in a date?")
                self.log.value["saved_time_minutes"] += 0.5
                self.update_log()

            else:
                print("Conversation is fine. Didnt do anything.")

        print("-> Done! checked all new conversations")
        return self.log

    def start(self):
        print("-> start()")
        import random

        while True:
            # check if session expired - if true, reload page
            # TODO

            self.check_conversations()
            wait_time = random.randint(10, 20)
            print(
                "-> wait for {} seconds and search again for new messages".format(
                    wait_time
                )
            )
            time.sleep(wait_time)


Website().start()
