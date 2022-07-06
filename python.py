from ast import Num
from copyreg import constructor
import string


print(“the value of 3 + 5”, 3 + 5)
print(“the value of 3 - 5”, 3 - 5)
print(“the value of 3 / 5”, 3 / 5)
print(“the value of 3 ** 5”, 3 ** 5)
print(“the value of 3 // 5”, 3 // 5)
print("this is a \"")

mls = '''this is a multiline string 
hello 
I will
keep going '''
print(mls)

print("%s to the right" %('this is a string'))
print('this is a 1', endl="") #endl = "" will continue the following statment in single line. opposite of endl.
print('this is a 2')

print ("this " * 50) #this will print this 50 times 

#lists

colleges = ['IIT', 'NIT', 'coe']
print(colleges[0])
print(colleges[1:3])

list2 = ['table', 'hair', 'fan', 'cloths']
list2.append('microphone')

list2.insert(3, 'pant')

list2.remove('pant')

print(list2 + ['pillow', 'tubelight', 'bed'])

print(len(list2))

print(max(list2)) #will print the maximum value alphabetically
print(min(list2)) #will print the minimum value alphabetically o/p bed

#tuples

tup1 = (1, 2, 4)
print(tup1[0])
tup1[0] = 6 # this will be an error as tuple is immutable 
 
list1 = list(tup1) #this is a type cast from tuple to list 

#dictionaries 

names = {'wasim': 26, 'almas': 25
'karan': 22}

print(names['almas'])
names['karan'] = 25 #this will change the value

print(names.keys())
print(names.values())

#if else statements 

print("enter you marks: ")
numb = int(input()) #we use the type casting as the input value returns a string 
print(numb)

if(numb > 90):
    grade = 'A'
elif (numb>80 and numb<90):
    grade = 'B'
elif (numb>100 or numb<0):
    grade = 'invalid'
else:
    grade = 'Dont know'

print("the grade is: ", grade)

#loops 
# for loops
print ("how many times do you want to execute")
num = int(input())
for i in range(0, num):
    print(i)

list3 = ['1', '2', '3']
for item in list3:
    print(item)

list4 = [[1, 2, 3], [7, 8, 9], [4, 5, 6]]
for item in list4:
    for i in item:
        print(i) 

#while loops 

print("enter a number")
number = int(input())

while(number>4): #it will print till the statement gets falls 
    print("number is greater than 4")
    number = int(input())
    if (number == 9):
        break # when number is 9 then the loop will break
    if (number == 5):
        continue #when the number is 5 then the below code will be ignored and it will continue the while loop  
    print("loop ended ")

#functions 

def avg1 (num1, num2):
    return (num1 + num2)/2
print(avg1(2, 3))


# string

str = "this is me"
print(str[0:2])
print(str[0:-2])
print(str[-2:])

print(str.capitalize())
print(str.find("thisd")) # -1 o/p will show that the required value is not in the string 

print(str.replace(" is ", "are"))

#file IO

file1 = open("wasim.txt", "wb") #wb means write mode 
print(file1.mode)
print(file1.name)

file1.write(bytes("write this to my file"))
file1.close() #if we dont close the file then other programs wont be able to access it, hence we need to close after use. 

#file io reading the content of the file

file1 = open('harry.txt', 'r+') #r+ means read and write

text_to_read = file1.read()
print(text_to_read)

# oops

 class Employee:
    __name = None
    __id = 0
    __salary = 0 #double underscore means those are private members 

    def set_name(self, name): #self is the object 
        self.__name = name
    def get_name(self):
        return self.__name

    def set_id(self, id): #self is the object 
        self.__id = id
    def get_id(self):
        return self.__id
    
    def set_salary(self, salary): #self is the object 
        self.__salary = salary
    def get_salary(self):
        return self.__salary
    
wasim = Employee()
# print(wasim.__name) #unable to access as the member is a private member to access it we will create a function 
harry.set_name('wasim')
print(wasim.get_name())


# constructor 
class Emp:
def __init__(self, name, id, salary):
    self.__name = name
    self.__id = id
    self.__salary = salary
almas = Emp('wasim', 007, 450000000)

