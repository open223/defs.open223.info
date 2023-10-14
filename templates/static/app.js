(function() {
    const search = document.getElementById("search");
    search.addEventListener("change", function() {
        for (const item of document.getElementsByClassName("card")) {
            // if search.value is empty, then show all
            if (search.value == "") {
                item.style.display = "block";
                continue;
            }
            // if search.value is not empty OR
            // if the 'language-turtle' section of the card contains the string,
            // then show the card
            // else hide the card
            if (item.dataset.concept.toLowerCase().indexOf(search.value) > -1) {
                item.style.display = "block";
            } else {
                item.style.display = "none";
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
