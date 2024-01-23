
var canvas = document.getElementById("cell_canvas");
var ctx = canvas.getContext('2d');
const canvasW = canvas.width;
const canvasH = canvas.height;

function draw() {
    ctx.fillStyle = '#f00';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(100,50);
    ctx.lineTo(50, 100);
    ctx.lineTo(0, 90);
    ctx.closePath();
    ctx.fill();
}

function draw_grid() {
    
}

function draw_square(x, y, size, color) {
    // size: square len in pixels
    // color: fill color of square
    // x, y: top left corner of square
    let sq_points = [[x, y],
                    [x+size, y],
                    [x+size, y+size],
                    [x, y+size]];
    return draw_polygon(sq_points, color);
}

function draw_polygon(points, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) {
        p = points[i];
        ctx.lineTo(p[0], p[1]);
    }
    ctx.closePath();
    ctx.fill();
}

function draw_circle(x, y, radius, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.ellipse(x, y, radius, radius, 0, 0, Math.PI*2);
    ctx.fill();
}

function gen_points(n, xmax, ymax) {
    let points = [];
    for (let i = 0; i < n; i++) {
        points.push(random_point(xmax, ymax));
    }
    return points;
}

function random_point(xmax, ymax) {
    return [random_int(xmax), random_int(ymax)];
}

function random_int(max) {
    return Math.floor(Math.random() * max);
}

draw_polygon(gen_points(20, canvasW, canvasH), '#f00');
draw_square(20, 20, 40, '#f0f');
draw_square(60, 20, 40, '#fa0');
draw_square(20, 60, 40, '#00f');
draw_square(60, 60, 40, '#0aa');
draw_circle(100, 100, 40, '#000');
