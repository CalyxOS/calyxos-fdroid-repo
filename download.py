#!/usr/bin/env python3

import json
import os
import re
import requests
import shutil
import subprocess
from urllib.parse import urlsplit

import fdroidserver.common
import fdroidserver.index

index = {}
etag = None

def main():
  with open("apks.json") as file:
    apks = json.load(file)
  if os.path.isfile("cache/versions.json"):
    with open("cache/versions.json") as file:
      versions = json.load(file)
  else:
    versions = {}
  for apk in apks:
    ver = ""
    ignore = False
    if "ignoreErrors" in apk:
      ignore = apk["ignoreErrors"]
    if "version" in apk:
      verObj = apk["version"]
      if "json" in verObj:
        ver = get_version_json(verObj["url"], verObj["json"])
      elif "regex" in verObj:
        ver = get_version_regex(verObj["url"], verObj["regex"])
      elif "fdroid" in verObj:
        ver = get_version_fdroid(apk["baseUrl"].format(ver="?fingerprint=" + verObj["fingerprint"]), verObj["fdroid"], ignore)
      if apk["name"] in versions and ver == versions[apk["name"]]:
        continue
      versions[apk["name"]] = ver
    print("Downloading " + apk["name"] + " " + ver)
    if "architectures" in apk:
      for arch in apk["architectures"]:
        download(apk["name"] + ".apk", apk["baseUrl"].format(arch=arch, ver=ver), ignore)
    else:
      download(apk["name"] + ".apk", apk["baseUrl"].format(ver=ver), ignore)
  with open('cache/versions.json', 'w') as file:
    json.dump(versions, file, ensure_ascii=False)

def download(name, download_url, ignore):
  if download_url.endswith(".apk"):
    #if os.path.isfile("fdroid/repo/" + name):
    #  os.rename("fdroid/repo/" + name, "fdroid/repo/" + os.path.split(urlsplit(download_url).path)[-1])
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-N", "-P", "fdroid/repo", download_url])
    if retcode == 0:
      os.rename("fdroid/repo/" + os.path.split(urlsplit(download_url).path)[-1], "fdroid/repo/" + name)
  else:
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-nc", "--content-disposition", "-P", "fdroid/repo", download_url])
  if not ignore and retcode != 0:
    raise Exception("Failed downloading " + download_url)

def get_version_regex(url, query):
  request = requests.get(url)
  regex = re.search(query, request.text)
  return regex.group(1)

def get_version_json(url, query):
  request = requests.get(url)
  version = request.json()
  if not isinstance(query, list):
    return version[query]
  for query_part in query:
    version = version[query_part]
  return version

def get_fdroid_index(url, ignore):
  global index
  global etag
  fdroidserver.common.config = {}
  fdroidserver.common.config['jarsigner'] = shutil.which('jarsigner')
  new_index, new_etag = fdroidserver.index.download_repo_index(url, etag)
  if new_index is not None:
    index = new_index
    etag = new_etag
  return index

def is_fdroid_apk_compatible(apk):
  if not 'nativecode' in apk:
    return True
  for abi in apk['nativecode']:
    if abi == "arm64-v8a":
      return True
    if abi == "armeabi-v7a":
      return True
    if abi == "armeabi":
      return True

def get_version_fdroid(url, query, ignore):
  data = get_fdroid_index(url, ignore)
  for app in data['apps']:
    if app['packageName'] == query:
      for apk in data['packages'][app['packageName']]:
        # No idea why suggestedVersionCode is a string
        if apk['versionCode'] >= int(app['suggestedVersionCode']):
          if is_fdroid_apk_compatible(apk):
            return apk['apkName']
      # Fallback to first compatible apk
      for apk in data['packages'][app['packageName']]:
        if is_fdroid_apk_compatible(apk):
          return apk['apkName']

if __name__ == "__main__":
  main()
