#include <iostream>
#include <cmath>

using namespace std;

class Point {
public:
    int x, y;

    Point(int x, int y);

    float coordinates() const;
};

Point::Point(int x, int y) {
    this->x = x;
    this->y = y;
}

float Point::coordinates() const {
    return sqrt (((x * x) + (y * y)));
 }

int main(void) {
    Point p1(3,4);
    cout << "Length of the point P1 from the origin: " << p1.coordinates() << endl;
    return EXIT_SUCCESS;
}