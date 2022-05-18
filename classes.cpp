#include <iostream>
using namespace std;
class complex{
    int a, b;
    public:
    void setdata(int x, int y){
        a = x;
        b = y;
    }
    void getdata(){
        cout<<"the complex number is: "<<a<<" + "<<b<<"i"<<endl;
    }
};
int main(){
    
    //here we have used to print 3 different forms to create and object and call the function. 

    complex c1;
    c1.setdata(4,3);
    c1.getdata();

//XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    // complex c1;
    // complex * ptr = &c1;
    // (*ptr).setdata(4,3);
    // (*ptr).getdata();

//XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

    // complex * ptr = new complex; //complex *ptr = new complex[3]; this is used to create 3 pointers 
    
    complex *ptr = &c1; //complex *ptr = new complex[3]; this is used to create 3 pointers 
    ptr->setdata(4,3);
    ptr->getdata();

    // all the above form are same 
    return 0;
}