import os
from tkinter import E
import win32api
import win32gui
import win32con
import subprocess
import json
import datetime
import time
import signal
import requests
import pyautogui
import keyboard
import concurrent.futures
import Common as data
from winreg import *
from PIL import Image
from PIL import ImageChops
from selenium import webdriver
from selenium.webdriver.common.by import By
from appium import webdriver as appiumWebDriver
from AUTODIS.tools import common_data as commonData
from AUTODIS.tools import mylogger as myLog
from AUTODIS.base import keyword
from robot.libraries.BuiltIn import BuiltIn

class CommonSupport(object):
    def __init__(self):
        self._web = commonData.webDriver

    def _get_data(self):
        robot_data = BuiltIn().get_variables()
        return {k[2:-1]:v for k,v in robot_data.items()}

    def _get_black_pixels(self, image):
        black_and_white_version = image.convert('1')
        black_pixels = black_and_white_version.histogram()[0]
        return black_pixels

    def _snap_and_compare(self, ss_region, baseLocation):
        name = baseLocation.split("\\")[4][:-9]
        ss_img = pyautogui.screenshot(region=ss_region)

        base = Image.open(baseLocation)
        diff = ImageChops.difference(base.convert("RGBA"), ss_img.convert("RGBA"))
        black_pixels = self._get_black_pixels(diff)
        total_pixels = diff.size[0] * diff.size[1]
        similarity_ratio = black_pixels/total_pixels
        if similarity_ratio < 0.995:
            # Save differed image in Captures folder
            isExist = os.path.exists(data.capturePath)
            if not isExist:
                os.makedirs(data.capturePath)
            ss_img.save(data.capturePath + "\\" + name + ".png")
            return name + " snapshot differs from baseline image.\n"
        else:
            return ""

    def _setup_winappdriver(self, prodExecPath, checkSplash=False, splashBaseImg=None):
        desired_caps = {}
        desired_caps["app"] = prodExecPath
        desired_caps["platformName"] = "Windows"
        desired_caps["deviceName"] = "WindowsPC"
        if not "Setup.exe" in prodExecPath:
            desired_caps["ms:waitForAppLaunch"] = 50
        else:
            desired_caps["ms:waitForAppLaunch"] = 10

        def launch_product():
            driver = appiumWebDriver.Remote(command_executor='http://' + data.ipAddr + ':' + data.WinAppDriverPort, desired_capabilities= desired_caps)
            return driver

        def check_splash():
            time.sleep(6)
            splashRegion = pyautogui.locateOnScreen(splashBaseImg, confidence=0.99)
            splashResult = self._snap_and_compare(splashRegion, splashBaseImg)
            return splashResult

        try:
            cmd = [data.WinAppDriverPath, data.ipAddr, data.WinAppDriverPort]
            winappdriver = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, shell=False)
            time.sleep(10)
            wadHandle = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(wadHandle, win32con.SW_MINIMIZE)
            inspect = subprocess.Popen(data.inspectPath, shell=False)
            time.sleep(10)
            inspectHandle = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(inspectHandle, win32con.SW_MINIMIZE)

            if checkSplash:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(launch_product), executor.submit(check_splash)]
                    returnValues = [f.result() for f in futures]
                    driver = returnValues[0]
                    splashResult = returnValues[1]
                    time.sleep(10)
                    return winappdriver, driver, inspect, splashResult
            else:
                driver = launch_product()
                time.sleep(10)
                return winappdriver, driver, inspect

        except Exception as e:
            inspect.terminate()
            winappdriver.terminate()
            raise Exception("Failed to setup WinAppDriver: " + str(e))

    def _get_File_Properties(self, fname):
        #==============================================================================
        """
        Read all properties of the given file return them as a dictionary.
        """
        notUsedPropNames = ('Comments', 'InternalName', 'ProductName',
            'CompanyName', 'LegalCopyright', 'ProductVersion',
            'FileDescription', 'LegalTrademarks', 'PrivateBuild',
            'FileVersion', 'OriginalFilename', 'SpecialBuild')
        propNames = ('ProductName', 'ProductVersion', 'LegalCopyright')
        props = {'FixedFileInfo': None, 'StringFileInfo': None, 'FileVersion': None}

        try:
            # backslash as parm returns dictionary of numeric info corresponding to VS_FIXEDFILEINFO struc
            fixedInfo = win32api.GetFileVersionInfo(fname, '\\')
            props['FixedFileInfo'] = fixedInfo
            props['FileVersion'] = "%d.%d.%d.%d" % (fixedInfo['FileVersionMS'] / 65536,
                    fixedInfo['FileVersionMS'] % 65536, fixedInfo['FileVersionLS'] / 65536,
                    fixedInfo['FileVersionLS'] % 65536)

            # \VarFileInfo\Translation returns list of available (language, codepage)
            # pairs that can be used to retreive string info. We are using only the first pair.
            lang, codepage = win32api.GetFileVersionInfo(fname, '\\VarFileInfo\\Translation')[0]

            # any other must be of the form \StringfileInfo\%04X%04X\parm_name, middle
            # two are language/codepage pair returned from above

            strInfo = {}
            for propName in propNames:
                strInfoPath = u'\\StringFileInfo\\%04X%04X\\%s' % (lang, codepage, propName)
                ## print str_info
                strInfo[propName] = win32api.GetFileVersionInfo(fname, strInfoPath)

            props['StringFileInfo'] = strInfo
        except Exception as e:
            raise Exception(str(e) + "\n" + fname)

        return fname, props['FileVersion'], strInfo['ProductName'], strInfo['ProductVersion'], strInfo['LegalCopyright']

    def _check_File_Properties(self, file_path, releaseYear, base_prodver, base_filever, base_prodname):
        fname, filever, prodname, prodver, cpyright = self._get_File_Properties(file_path)

        # check file version, product version, product name and copyright
        if prodver == base_prodver and prodname == base_prodname:
            if not int(releaseYear) - 1 in cpyright or not filever == base_filever:
                raise Exception("Information in " + file_path + " is incorrect!\n" + prodname + "\n" + cpyright + "\n" +
                    prodver + "\n" + filever)
        
            # check for digital signature
            cmd = '"' + "(Get-AuthenticodeSignature -FilePath " + "'" + file_path + "').Status -eq 'Valid'" + '"'
            signValidity = subprocess.getoutput(data.powershell_path + " -Command " + cmd)
            if signValidity == "False":
                raise Exception(file_path + " is not digitally signed.")

    def _check_logfile_for_error(self, logfile_directory, baseline_path):
        baseline = open(baseline_path, "r").read().splitlines()
        logMatches = 0
        for root, dir, files in os.walk(logfile_directory):
            # if there is already a matching logfile
            if logMatches == 1:
                break
            for file in files:
                # check log files that are generated at launch
                if file.startswith("Drawing1"):
                    log_path = os.path.join(logfile_directory, file)
                    actual = open(log_path, "r").read().splitlines()
                    # check if log files' length are the same
                    if not len(baseline) == len(actual):
                        continue
                    # check log file for any difference
                    for count, value in enumerate(actual):
                        # exclude first line (timestamp)
                        if count == 0:
                            continue
                        if not value == baseline[count]:
                            break
                        if count == len(baseline) - 1:
                            logMatches = 1
        if logMatches == 0:
            raise Exception("No matching log files detected")

    def _check_version_dictionary(self, dictionary, autocadPath):
        for component, extVerExclTuple in dictionary.items():
            extension = extVerExclTuple[0]
            version = extVerExclTuple[1]
            exclusions = extVerExclTuple[2]
            for file in os.listdir(autocadPath):
                if file.endswith(extension) and file.startswith(component):
                    fname, filever, prodname, prodver, cpyright = self._get_File_Properties(autocadPath + "\\" + file)
                    if filever == version:
                        pass
                    elif file in exclusions:
                        pass
                    else:
                        raise Exception(fname + " version of " + filever + " is wrong. Expected " + version)

    @keyword
    @myLog.MyErrorHandler
    def launch_installer(self, masterLocation, snapshotDict, productName):

        setupPath = masterLocation + "/Setup.exe"
        result = ""
        
        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(setupPath)
        try:
            time.sleep(60)
            installHandle = hex(int(win32gui.GetForegroundWindow()))
            desired_caps = {}
            desired_caps["appTopLevelWindow"] = installHandle
            driver = appiumWebDriver.Remote(command_executor='http://' + data.ipAddr + ':' + data.WinAppDriverPort, desired_capabilities= desired_caps)

            driver.find_element_by_name("I agree to the Terms of Use").click()
            time.sleep(2)
            driver.find_element_by_name("Next").click()
            time.sleep(2)

            # Install Directory Dialog Check
            installDirBaseImg = snapshotDict["installDirectory"]
            installDirRegion = pyautogui.locateOnScreen(installDirBaseImg, confidence=0.99)
            result += self._snap_and_compare(installDirRegion, installDirBaseImg)

            if productName == "ACE":
                driver.find_element_by_name("Next").click()
                time.sleep(2)
                driver.find_element_by_name("Content Migration Utility for AutoCAD Electrical ").click()
                time.sleep(2)

            driver.find_element_by_name("Install").click()
            time.sleep(2)

            # Install Progress Dialog Check
            installProgBaseImg = snapshotDict["installProgress"]
            installProgRegion = pyautogui.locateOnScreen(installProgBaseImg, confidence=0.99)
            result += self._snap_and_compare(installProgRegion, installProgBaseImg)

            elaspedTime = 0
            while elaspedTime < 1800:
                try:
                    if productName == 'ACE':
                        completeText = driver.find_element_by_name("Install complete")
                        processID = int(completeText.get_attribute("ProcessId"))
                    else:
                        driver.find_element_by_name("Not now").click()
                except:
                    time.sleep(60)
                    elaspedTime += 60
                else:
                    break

            if elaspedTime >= 1800:
                raise Exception("Product failed to install")

            time.sleep(2)
            if productName == 'ACE':
                os.kill(processID, signal.SIGTERM)
            else:
                driver.find_element_by_name("Finish").click()

            if result:
                raise Exception("")
                
        except Exception as e:
            raise Exception(str(e) + result)

        finally:
            return (winappdriver, driver, inspect)

    @keyword
    @myLog.MyErrorHandler
    def close_drivers(self, driverInfo):
        driverInfo[2].terminate()
        driverInfo[0].terminate()

    @keyword
    @myLog.MyErrorHandler
    def check_loose_files(self, path, releaseYear, base_prodver, base_filever, base_prodname):
        for file in os.listdir(path):
            # check only dll, arx and fas files
            if file.endswith('.dll') or file.endswith('.arx') or file.endswith('.fas'):
                file_path = os.path.join(path, file)
                self._check_File_Properties(file_path, releaseYear, base_prodver, base_filever, base_prodname)
                
    @keyword
    @myLog.MyErrorHandler
    def check_component_version(self, autoCADPath, localMF, prdName, prdExec, instPath, ltuVersion):

        if prdName == "ACE":
            prdName = "Acade"
        elif prdName == "ACM":
            prdName = "Acadm"
        
        # Component Version Dictionary
        versionDict = {
            autoCADPath + '\\' + prdExec : os.environ["ACAD_VER"],
            localMF + '/ODIS/AdODIS-installer.exe' : os.environ["ODIS_VER"],
            localMF + '/x86/Licensing/AdskLicensing-installer.exe' : os.environ["LICENSINGINSTALL_VER"],
            autoCADPath + '\\AdskLicensingSDK_6.dll' : os.environ["LICENSINGSDK_VER"],
            data.AutodeskSharedx86Path + '\\AdskLicensing\\' + os.environ["LICENSINGFILE_VER"] + '\\AdskLicensingService\\AdskLicensingService.exe' : os.environ["LICENSINGSERVICE_VER"],
            data.AutodeskSharedx86Path + '\\AdskLicensing\\' + os.environ["LICENSINGFILE_VER"] + '\\AdskLicensingAgent\\AdskLicensingAgent.exe' : os.environ["LICENSINGAGENT_VER"],
            data.AutodeskSharedx86Path + '\\AdskLicensing\\' + os.environ["LICENSINGFILE_VER"] + '\\helper\\AdskLicensingInstHelper.exe' : os.environ["LICENSINGHELPER_VER"],
            data.AutodeskSharedx86Path + '\\Adlm\\' + ltuVersion + '\\LTU.exe' : os.environ["LTU_VER"],
            data.AutodeskSharedx86Path + '\\Adlm\\' + ltuVersion + '\\LMU.exe' : os.environ["LMU_VER"],
            instPath + '\\Autodesk AdSSO\\AdSSO.exe' : os.environ["ADSSO_VER"],
            autoCADPath + '\\AdMaterialUI.dll' : os.environ["CMUI_VER"],
            autoCADPath + '\\AdpSDKCore.dll' : os.environ["ADP_VER"],
            data.AutodeskSharedPath + '\\Inventor Interoperability 2023\\Bin\\AmSrv.dll' : os.environ["INVENTORSERVER_VER"],
            autoCADPath + '\\AdSpatialReference.dll' : os.environ["ADSPATIALREF_VER"],
            autoCADPath + '\\CER\\senddmp.exe' : os.environ["SENDDMP_VER"],
            autoCADPath + '\\CER\\en-US\\senddmp.resources.dll' : os.environ["SENDDMPRES_VER"],
            autoCADPath + '\\' + prdName + '\\UPI\\UPI.dll' : os.environ["UPI_VER"],
            autoCADPath + '\\' + prdName + '\\UPI\\UPICA.dll' : os.environ["UPICA_VER"]
        }

        # Check every component-version mapping matches that in versionDict
        for component, version in versionDict.items():
            fname, filever, prodname, prodver, cpyright = self._get_File_Properties(component)
            if filever == version:
                pass
            elif "AdODIS-installer.exe" in component and prodver == version:
                pass
            else:
                raise Exception(fname + " version of " + filever + " is wrong. Expected " + version)

    @keyword
    @myLog.MyErrorHandler
    def check_multiple_component_version(self, autocadPath, prdSpecificDict=None):

        # Common Component Version Dictionary for files with similar naming convention
        # e.g. OGS*.dll, atf*.dll, ASM*228A.dll
        # Format: startingString : (endingString, version, exclusions)
        commonDict = {
            "OGS" : (".dll", os.environ["OGS_VER"], []),
            "atf" : (".dll", os.environ["ATFSDK_VER"], []),
            "ASM" : ("228A.dll", os.environ["ASM_VER"], [])
        }

        self._check_version_dictionary(commonDict, autocadPath)
        if not prdSpecificDict == None:
            self._check_version_dictionary(prdSpecificDict, autocadPath)

    @keyword
    @myLog.MyErrorHandler
    def validate_bootstrap(self, masterFolder):
        filePath = os.path.join(masterFolder, "ODIS\\bootstrap.json")
        f = open(filePath)
        data = json.load(f)
        if not data['state'] == "live":
            raise Exception("State is not set to live")
        elif not data['env'] == "prd":
            raise Exception("Environment is not set to production")
        else:
            pass

    @keyword
    @myLog.MyErrorHandler
    def activate_product(self, licenseType, prodExecPath, snapshotDict, username=None, password=None):

        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(prodExecPath)
        lgsResult = ""

        try:
            if not licenseType == 'odnetwork':
                # Take snapshot of LGS dialog
                lgsBaseImg = snapshotDict["lgs"]
                lgsRegion = pyautogui.locateOnScreen(lgsBaseImg, confidence=0.99)
                lgsResult = self._snap_and_compare(lgsRegion, lgsBaseImg)

            # Trigger UI elements
            if licenseType == 'network':
                try:
                    driver.find_element_by_accessibility_id("btn-select-nw").click()
                    time.sleep(5)
                    lgsProcID = driver.find_element_by_name("Single License Server").get_attribute("ProcessId")
                    driver.find_element_by_xpath("//*[@LocalizedControlType=\"edit\"][@ProcessId=" + str(lgsProcID) + "]").send_keys(data.networkLicense)
                    time.sleep(5)
                    driver.find_element_by_accessibility_id("done").click()
                    time.sleep(20)
                    driver.find_element_by_accessibility_id("1002").click()
                    time.sleep(5)
                    driver.find_element_by_name("New").click()
                    time.sleep(5)
                    try:
                        driver.find_element_by_name("Open").click()
                    except:
                        pass
                    time.sleep(10)
                    driver.find_element_by_accessibility_id("local:AutoCompleteEdit_1").send_keys("LOGFILEON" + "\n" + "QUIT" + "\n")
                    time.sleep(5)
                except Exception as e:
                    raise e

            elif licenseType == 'singleuser':
                try:
                    driver.find_element_by_name("Sign in with your Autodesk ID").click()
                    time.sleep(10)
                    driver.find_element_by_name("Email text field").click()
                    driver.find_element_by_name("Email text field").send_keys(data.GetFormattedCredential(username))
                    time.sleep(5)
                    driver.find_element_by_name("Next button").click()
                    time.sleep(5)
                    driver.find_element_by_name("Password text field").click()
                    driver.find_element_by_name("Password text field").send_keys(data.GetFormattedCredential(password))
                    time.sleep(5)
                    driver.find_element_by_name("Sign in button").click()
                    time.sleep(20)
                    driver.find_element_by_accessibility_id("1002").click()
                    time.sleep(5)
                    driver.find_element_by_name("New").click()
                    time.sleep(5)
                    try:
                        driver.find_element_by_name("Open").click()
                    except:
                        pass
                    time.sleep(10)
                    driver.find_element_by_accessibility_id("local:AutoCompleteEdit_1").send_keys("LOGFILEON" + "\n" + "QUIT" + "\n")
                    time.sleep(5)
                except Exception as e:
                    raise e

            elif licenseType == 'odnetwork':
                try:
                    driver.find_element_by_accessibility_id("1002").click()
                    time.sleep(5)
                    driver.find_element_by_name("New").click()
                    time.sleep(5)
                    try:
                        driver.find_element_by_name("Open").click()
                    except:
                        pass
                    time.sleep(10)
                    driver.find_element_by_accessibility_id("local:AutoCompleteEdit_1").send_keys("LOGFILEON" + "\n" + "QUIT" + "\n")
                    time.sleep(5)
                except Exception as e:
                    raise e

            else:
                raise Exception("Wrong license type")

            if lgsResult:
                raise Exception("")

        except Exception as e:
            if licenseType == "odnetwork":
                raise e
            else:
                raise Exception(str(e) + lgsResult)

        finally:
            # Close WinAppDriver
            inspect.terminate()
            winappdriver.terminate()

    @keyword
    @myLog.MyErrorHandler
    def check_error_on_first_launch(self, prodExecPath, acaLogDirectory, baseLogPath):

        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(prodExecPath)
        appTitleBar = driver.find_element_by_accessibility_id(data.titleBarID)
        appProcID = int(appTitleBar.get_attribute("ProcessId"))

        try:
            # Trigger UI elements
            appTitleBar.click()
            time.sleep(2)
            driver.find_element_by_name("New").click()
            time.sleep(5)
            try:
                driver.find_element_by_name("Open").click()
            except:
                pass
            time.sleep(5)
            self._check_logfile_for_error(acaLogDirectory, baseLogPath)
        
        except Exception as e:
            raise e

        finally:
            # Close WinAppDriver
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()

    @keyword
    @myLog.MyErrorHandler
    def set_system_time_after_timebomb(self, ReleaseYear):
        time_tuple = (int(ReleaseYear) - 1,  # Year
                      6,  # Month
                      3,  # Day
                      0,  # Hour
                      0,  # Minute
                      0,  # Second
                      0,  # Millisecond
                     )
        dayOfWeek = datetime.datetime(*time_tuple).isocalendar()[2]
        t = time_tuple[:2] + (dayOfWeek,) + time_tuple[2:]
        win32api.SetSystemTime(*t)

    def reset_system_time(self):
        timeapi = requests.get("http://worldtimeapi.org/api/timezone/Etc/GMT")
        tuple_info = timeapi.json()['datetime']
        api_tuple = (int(tuple_info[0:4]), # Year
                     int(tuple_info[5:7]), # Month
                     int(tuple_info[8:10]), # Day
                     int(tuple_info[11:13]), # Hour
                     int(tuple_info[14:16]), # Minute
                     int(tuple_info[17:19]), # Second
                     0, # Millisecond
                    ) 
        dayOfWeek = datetime.datetime(*api_tuple).isocalendar()[2]
        t = api_tuple[:2] + (dayOfWeek,) + api_tuple[2:]
        win32api.SetSystemTime(*t)

    @keyword
    @myLog.MyErrorHandler
    def launch_and_run_smoketest(self, prodExecPath, smoketest):
        
        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(prodExecPath)
        appTitleBar = driver.find_element_by_accessibility_id(data.titleBarID)
        appProcID = int(appTitleBar.get_attribute("ProcessId"))

        try:
            # Trigger UI elements
            appTitleBar.click()
            time.sleep(2)
            driver.find_element_by_name("New").click()
            time.sleep(5)
            try:
                driver.find_element_by_name("Open").click()
            except:
                pass
            time.sleep(15)
            cmdline = driver.find_element_by_accessibility_id("local:AutoCompleteEdit_1")
            for c in smoketest:
                cmdline.send_keys(c)
                if c == "\n":
                    time.sleep(2)
                else:
                    time.sleep(0.1)
            time.sleep(5)
            return appProcID, inspect, winappdriver

        except:
            # Close all windows
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()
            raise Exception("Error running smoketest")

    @keyword
    @myLog.MyErrorHandler
    def check_timebomb(self, prodExecPath, snapshotDict, smokeTest):
        
        appProcID, inspect, winappdriver = self.launch_and_run_smoketest(prodExecPath, smokeTest)

        try:
            # Check timebomb
            smokeBaseImg = snapshotDict["smoke"]
            smokeRegion = pyautogui.locateOnScreen(smokeBaseImg, confidence=0.99)
            timebombResult = self._snap_and_compare(smokeRegion, smokeBaseImg)
            if timebombResult:
                raise Exception(timebombResult)
        
        except Exception as e:
            raise e

        finally:
            # Close all windows
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()
            self.reset_system_time()

    @keyword
    @myLog.MyErrorHandler
    def check_pit_file(self, prdKey, prdLicVer):
        
        # open PitViewer URL
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = webdriver.Chrome(options=options, executable_path=data.chromedriverPath)
        driver.get(data.url_pit_viewer)
        time.sleep(1)

        # upload PIT file
        uploadElement = driver.find_element(By.ID, 'pitfileUploadCtrl')
        time.sleep(1)
        uploadElement.send_keys(data.pitPath)
        time.sleep(1)

        # open PIT file
        driver.find_element(By.ID, 'LoadBtn').click()
        driver.implicitly_wait(2)

        # get product key info
        prdInfo = driver.find_element_by_xpath("//div[@id='UpdatePanel1']/div[2]/span[1]").text
        time.sleep(1)
        driver.close()
        driver.quit()
        prdKeyStr = "ID= " + prdKey
        prdLicStr = "MSRT= " + prdLicVer

        # check that product key is correct
        if not prdKeyStr in prdInfo:
            raise Exception("Product key in PIT file is incorect. Expected " + prdKeyStr)
        # check for FCS license
        elif not prdLicStr in prdInfo:
            raise Exception("Product license version in PIT file is incorrect. Expected " + prdLicStr)
        else:
            pass

    @keyword
    @myLog.MyErrorHandler
    def check_about_dialog(self, licType, prodExecPath, snapshotDict):

        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(prodExecPath)
        result = ""

        try:
            appTitleBar = driver.find_element_by_accessibility_id(data.titleBarID)
            appProcID = int(appTitleBar.get_attribute("ProcessId"))
            # Trigger UI elements
            appTitleBar.click()
            time.sleep(2)
            driver.find_element_by_accessibility_id("ID_Help_FlyoutButtonShowFlyout").click()
            time.sleep(2)
            keyboard.send('down, down, down, enter')
            time.sleep(5)
            # Check About dialog version, copyright and branding
            aboutBaseImg = snapshotDict["about"]
            aboutRegion = pyautogui.locateOnScreen(aboutBaseImg, confidence=0.99)
            result += self._snap_and_compare(aboutRegion, aboutBaseImg)
            driver.find_element_by_accessibility_id("1534").click()
            time.sleep(5)
            # Check License Manager branding
            if licType == "network":
                licmBaseImg = snapshotDict["licManagerNetwork"]
            elif licType == "odnetwork":
                licmBaseImg = snapshotDict["licManagerOD"]
            else:
                licmBaseImg = snapshotDict["licManagerSingle"]
            licmRegion = pyautogui.locateOnScreen(licmBaseImg, confidence=0.99)
            result += self._snap_and_compare(licmRegion, licmBaseImg)
            licenseProc = driver.find_element_by_name("Clic LM").get_attribute("ProcessId")

            if licType == "network":
                try:
                    driver.find_element_by_xpath("//*[@LocalizedControlType=\"tab item\"]/*[@LocalizedControlType=\"button\"]").click()
                    time.sleep(5)
                    licenseElem = driver.find_elements_by_xpath("//*[@ProcessId=" + licenseProc + "][@LocalizedControlType=\"text\"]")[23]
                    time.sleep(5)
                    licenseId = licenseElem.get_attribute("Name")
                    # Check for FCS license
                    if not licenseId.endswith("F"):
                        raise Exception("License ID in About dialog is not FCS license.")
                    else:
                        pass
                
                except Exception as e:
                    raise e

                finally:
                    os.kill(int(licenseProc), signal.SIGTERM)

            if result:
                raise Exception("")
        
        except Exception as e:
            raise Exception(str(e) + result)

        finally:
            # Close all windows
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()

    @keyword
    @myLog.MyErrorHandler
    def check_version_in_logs(self, directory, vernum, aecver):
        logPath = ""
        for root, dir, files in os.walk(directory):
            for file in files:
                # check log file created during version test
                if file.startswith("VERSIONTEST"):
                    logPath = os.path.join(directory, file)
                    break
            break
        log = open(logPath, "r").read()
        lines = log.splitlines()
        os.remove(logPath)
        os.remove(data.verDwgSaveLocation)

        # check for correct version numbers
        for line in lines:
            if "_VERNUM = " in line and not (vernum in line):
                raise Exception("VERNUM is wrong")
            if "FileVersion:" in line and not(aecver in line):
                raise Exception("AECVER is wrong")

    @keyword
    @myLog.MyErrorHandler
    def check_swidtag(self, swid_path, prodname, tagid, version):
        with open(swid_path) as f:
            header = f.readline().casefold()
            prodname = ("name=" + "\"" + prodname + "\"").casefold()
            tagid = ("tagid=" + "\"" + tagid + "\"").casefold()
            version = "version=" + "\"" + version + "\""
            if (not prodname in header):
                raise Exception("SWIDTAG file has incorrect name")
            elif (not tagid in header):
                raise Exception("SWIDTAG file has incorrect tag ID")
            elif (not version in header):
                raise Exception("SWIDTAG file has incorrect version")
            else:
                pass

    @keyword
    @myLog.MyErrorHandler
    def check_online_help_url(self, regroot):
        aReg = ConnectRegistry(None,HKEY_LOCAL_MACHINE)
        aKey = OpenKey(aReg, regroot)
        info = QueryValueEx(aKey, "HelpBaseURL")[0]
        if not info == data.online_help_url:
            raise Exception("Error! " + data.online_help_url + " expected, but got " + info + " instead.")
        else:
            pass
        
    @keyword
    @myLog.MyErrorHandler
    def validate_app_home_url(self, path, baseData):
        filePath = os.path.join(path, "strings.resjson")
        f = open(filePath)
        data = json.load(f)
        try:
            for key, value in baseData.items():
                if not data[key] == value:
                    raise Exception("Value " + value + " expected for " + key + ", but got " + data[key] + " instead.")
                else:
                    pass
        except Exception as e:
            raise e

    @keyword
    @myLog.MyErrorHandler
    def check_branding(self, snapshotDict, directories, prodExecPath, licType):

        time.sleep(5)
        result = ""

        # Show Desktop
        pyautogui.keyDown('winleft')
        pyautogui.press('d')
        pyautogui.keyUp('winleft')

        # Desktop icons check
        if licType == "odnetwork":
            iconBaseImg = snapshotDict["iconOD"]
        else:
            iconBaseImg = snapshotDict["icon"]
        iconRegion = pyautogui.locateOnScreen(iconBaseImg, confidence=0.99)
        result += self._snap_and_compare(iconRegion, iconBaseImg)

        pyautogui.keyDown('winleft')
        pyautogui.press('d')
        pyautogui.keyUp('winleft')

        # ARP Check
        subprocess.call("C:\Windows\SysWOW64\control.exe C:\Windows\System32\\appwiz.cpl", shell=False)
        time.sleep(2)
        windowHandle = win32gui.FindWindow(None, 'Programs and Features')
        win32gui.SetForegroundWindow(windowHandle)
        windowBox = win32gui.GetWindowRect(windowHandle)
        if licType == "odnetwork":
            arpBaseImg = snapshotDict["arpOD"]
        else:
            arpBaseImg = snapshotDict["arp"]
        arpRegion = pyautogui.locateOnScreen(arpBaseImg, confidence=0.99)
        result += self._snap_and_compare(arpRegion, arpBaseImg)
        pyautogui.click(x=windowBox[2]-15, y=windowBox[1]+15)
        time.sleep(2)

        # Setup WinAppDriver and Appium (Splash Screen Check)
        winappdriver, driver, inspect, splashResult = self._setup_winappdriver(prodExecPath, checkSplash=True, splashBaseImg=snapshotDict["splash"])
        result += splashResult

        try:
            appTitleBar = driver.find_element_by_accessibility_id(data.titleBarID)
            appProcID = int(appTitleBar.get_attribute("ProcessId"))

            # Trigger UI elements
            appTitleBar.click()
            time.sleep(2)

            # App Home Check
            apphomeBaseImg = snapshotDict["apphome"]
            apphomeRegion = pyautogui.locateOnScreen(apphomeBaseImg, confidence=0.9)
            result += self._snap_and_compare(apphomeRegion, apphomeBaseImg)

            windowHandle = win32gui.GetForegroundWindow()
            windowBox = win32gui.GetWindowRect(windowHandle)
            pyautogui.click(x=windowBox[0]+15, y=windowBox[1]+15)
            time.sleep(5)

            # App Frame Check
            appframeBaseImg = snapshotDict["appframe"]
            appframeRegion = pyautogui.locateOnScreen(appframeBaseImg, confidence=0.99)
            result += self._snap_and_compare(appframeRegion, appframeBaseImg)

            driver.find_element_by_accessibility_id(data.titleBarID).click()
            driver.find_element_by_accessibility_id("ID_Help_FlyoutButtonShowFlyout").click()
            time.sleep(5)

            # Help Dropdown Check
            helpBaseImg = snapshotDict["help"]
            helpRegion = pyautogui.locateOnScreen(helpBaseImg, confidence=0.99)
            result += self._snap_and_compare(helpRegion, helpBaseImg)

            if result:
                raise Exception("")
        
        except Exception as e:
            raise Exception(str(e) + result)

        finally:
            # Close all windows
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()

    @keyword
    @myLog.MyErrorHandler
    def verify_account_log_in(self, prodExecPath, snapshotDict, smokeTest, username, password):

        # Setup WinAppDriver and Appium
        winappdriver, driver, inspect = self._setup_winappdriver(prodExecPath)
        appTitleBar = driver.find_element_by_accessibility_id(data.titleBarID)
        appProcID = int(appTitleBar.get_attribute("ProcessId"))

        try:
            # Trigger UI elements
            appTitleBar.click()
            time.sleep(2)
            driver.find_element_by_accessibility_id("loggedInImage").click()
            time.sleep(3)
            keyboard.send('down, enter')
            time.sleep(10)
            driver.find_element_by_name("Email text field").click()
            driver.find_element_by_name("Email text field").send_keys(data.GetFormattedCredential(username))
            time.sleep(2)
            driver.find_element_by_name("Next button").click()
            time.sleep(2)
            driver.find_element_by_name("Password text field").click()
            driver.find_element_by_name("Password text field").send_keys(data.GetFormattedCredential(password))
            time.sleep(2)
            driver.find_element_by_name("Sign in button").click()
            time.sleep(5)
            driver.find_element_by_name("New").click()
            time.sleep(5)
            try:
                driver.find_element_by_name("Open").click()
            except:
                pass
            time.sleep(10)
            cmdline = driver.find_element_by_accessibility_id("local:AutoCompleteEdit_1")
            for c in smokeTest:
                cmdline.send_keys(c)
                if c == "\n":
                    time.sleep(2)
                else:
                    time.sleep(0.1)
            time.sleep(5)

            # Smoke test
            smokeBaseImg = snapshotDict["smoke"]
            smokeRegion = pyautogui.locateOnScreen(smokeBaseImg, confidence=0.99)
            smokeResult = self._snap_and_compare(smokeRegion, smokeBaseImg)
            if smokeResult:
                raise Exception(smokeResult)
        
        except Exception as e:
            raise e

        finally:
            # Close all windows
            os.kill(appProcID, signal.SIGTERM)
            inspect.terminate()
            winappdriver.terminate()

    @keyword
    @myLog.MyErrorHandler
    def validate_smoketest_via_logs(self, smokeLogBaseline, logDir, testName):
        baseline = open(smokeLogBaseline, "r").read().splitlines()
        for root, dir, files in os.walk(logDir):
            for file in files:
                # check log file created during version test
                if file.startswith(testName):
                    logPath = os.path.join(logDir, file)
                    break
            break
        actual = open(logPath, "r").read().splitlines()

        try:
            # check if log files' length are the same
            if not len(baseline) == len(actual):
                raise Exception("Log files differ in length")
            # check log file for any difference
            for count, value in enumerate(actual):
                # exclude first line (timestamp)
                if count == 0:
                    continue
                if not value == baseline[count]:
                    raise Exception("Log files do not match")
        except Exception as e:
            raise e
        finally:
            os.remove(logPath)
            os.remove(data.smokeDwgSaveLocation)

    @keyword
    @myLog.MyErrorHandler
    def close_windows(self, appProcID, inspect, winappdriver):
        # Close all windows
        os.kill(appProcID, signal.SIGTERM)
        inspect.terminate()
        winappdriver.terminate()
        time.sleep(10)
