#include <cassert>
#include <iostream>
#include <string>
#include <math.h>

using namespace std;

class Point {
public:
    int x, y;

    Point(int x, int y);

    Point operator+(const Point &p2) const;
    Point operator+(int scalar) const;
    Point operator-(const Point &p2) const;
    Point operator*(int factor) const;

    Point add(const Point &p2) const; // "write-protect 'this'" - promise to use the instance read-only
    Point add(int scalar) const;

    string to_string() const;
    float coordinates(const Point &p4) const;
};

// -------------------------------

Point::Point(int x, int y) {
    this->x = x;
    this->y = y;
}

Point Point::operator+(const Point &p2) const {
    return add(p2);
}

Point Point::operator+(int scalar) const {
    return add(scalar);
}

Point Point::operator-(const Point &p2) const {
    return Point(x - p2.x, y - p2.y);
}

Point Point::operator*(int factor) const {
    return Point(x * factor, y * factor);
}

Point Point::add(const Point &p2) const {
    return Point(x + p2.x, y + p2.y);
}

Point Point::add(int scalar) const {
    return Point(x + scalar, y + scalar);
}

string Point::to_string() const {
    return "P(" + std::to_string(x) + ", " + std::to_string(y) + ")";
}

float Point::coordinates(const Point &p4) const {
    float length;
    length = ((p4.x) * (p4.x) + (p4.y) * (p4.y));
    return sqrt (length);
 }

int main(void) {
    Point p1(2, 3);
    assert(p1.to_string() == "P(2, 3)");

    Point p2(10, 10);

    // cout << "p1: " << p1.to_string() << endl;
    // cout << "p2: " << p2.to_string() << endl;

    // cout << "Now adding p1 + p2" << endl;
    Point p3 = p1 + p2;
    Point p4(3,4);

    // cout << "p1: " << p1.to_string() << endl;
    // cout << "p2: " << p2.to_string() << endl;
    // cout << "p3: " << p3.to_string() << endl;
    cout << "length of point P4 from origin: " << p4.coordinates(p4) << endl;
}