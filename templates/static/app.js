(function() {
    const search = document.getElementById("search");
    search.addEventListener("change", function() {
        for (const item of document.getElementsByClassName("card")) {
            if (item.dataset.concept.toLowerCase().indexOf(search.value) == -1) {
                item.style.display = "none";
            } else {
                item.style.display = "block";
            }
        }
    });
    for (const item of document.getElementsByClassName('a')) {
        item.click( function(e) {
            e.preventDefault();
            for (const item of document.getElementsByClassName("card")) {
                item.style.display = "block";
            }
            return false;
        });
    }
})();
