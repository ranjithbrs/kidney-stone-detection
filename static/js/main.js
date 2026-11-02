(function ($) {
    "use strict";

    // Spinner
    var spinner = function () {
        setTimeout(function () {
            if ($('#spinner').length > 0) {
                $('#spinner').removeClass('show');
            }
        }, 1);
    };
    spinner(0);
    
    
    // Initiate the wowjs
    new WOW().init();


    // Sticky Navbar
    $(window).scroll(function () {
        if ($(this).scrollTop() > 45) {
            $('.navbar').addClass('sticky-top shadow-sm');
        } else {
            $('.navbar').removeClass('sticky-top shadow-sm');
        }
    });


    // testimonial carousel
    $(".testimonial-carousel").owlCarousel({
        autoplay: true,
        smartSpeed: 1500,
        center: false,
        dots: true,
        loop: true,
        margin: 25,
        nav : true,
        navText : [
            '<i class="fa fa-angle-right"></i>',
            '<i class="fa fa-angle-left"></i>'
        ],
        responsiveClass: true,
        responsive: {
            0:{
                items:1
            },
            576:{
                items:1
            },
            768:{
                items:1
            },
            992:{
                items:2
            },
            1200:{
                items:2
            }
        }
    });


    // Facts counter
    $('[data-toggle="counter-up"]').counterUp({
        delay: 5,
        time: 2000
    });


   // Back to top button
   $(window).scroll(function () {
    if ($(this).scrollTop() > 300) {
        $('.back-to-top').fadeIn('slow');
    } else {
        $('.back-to-top').fadeOut('slow');
    }
    });
    $('.back-to-top').click(function () {
        $('html, body').animate({scrollTop: 0}, 1500, 'easeInOutExpo');
        return false;
    });


})(jQuery);


 // Fade-in rows one by one
const rows = document.querySelectorAll(".responsive-table tbody tr");

rows.forEach((row, index) => {
    row.style.opacity = "0";
    row.style.transform = "translateY(20px)";

    setTimeout(() => {
        row.style.transition = "all 0.5s ease";
        row.style.opacity = "1";
        row.style.transform = "translateY(0)";
    }, index * 120);
});

// Glow effect on heading
const heading = document.querySelector(".heading");

setInterval(() => {
    heading.style.textShadow =
        "0 0 10px #00d1f9,0 0 25px #00d1f9,0 0 40px #00d1f9";

    setTimeout(() => {
        heading.style.textShadow =
            "0 0 5px #00d1f9,0 0 15px #00d1f9";
    }, 800);
}, 1800);

