#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse

import itchat


def send(send_list):
    login()

    for msg in send_list:
        if os.path.isfile(msg):  # sends files
            print("sending file: {}".format(msg))

            itchat.send_file(msg, toUserName="filehelper")
        else:  # sends text msgs
            print("sending text message: {}".format(msg))

            itchat.send(msg, toUserName="filehelper")

        print("done")

    logout()


def receive(dest_file_path):
    login()

    print("receiving messages")

    @itchat.msg_register(["Text", "Picture", "Recording", "Attachment", "Video"])
    def download(msg):
        content = msg["Text"]

        if content == "#":  # "#" stops receiving and logs out wechat
            logout()
        else:
            try:  # receives files
                content(os.path.join(dest_file_path, msg["FileName"]))
                print("received file: {}".format(msg["FileName"]))
            except:  # receives text msgs
                print("received text message: \n{}".format(msg["Text"]))

    itchat.run()


def login():
    itchat.auto_login(enableCmdQR=2)


def logout():
    itchat.logout()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="wechat_file_helper.py - a tool for sending and receiving "
                                                 + "text messages and files from wechat file helper")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--send", "-s", action="store", nargs="+", dest="send_list",
                       help="send text messages or files")
    group.add_argument("--receive", "-r", action="store_true", help="receive text messages or files")

    parser.add_argument("--path", "-p", action="store", dest="path", default="/home/neko/Downloads/",
                        help="path for storing downloaded files")

    args = parser.parse_args()

    # checks if the path exists
    if args.path and not os.path.exists(args.path):
        print("wechat_file_helper.py: error: path not exists")
        exit(1)

    if args.send_list:
        send(args.send_list)
    elif args.receive:
        receive(args.path)
