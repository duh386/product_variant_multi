openerp.product_variant_multi = function(instance) {

    var files = ["multi","multi_template_widget"];
    for(var i=0; i<files.length; i++) {
        if(openerp.product_variant_multi[files[i]]) {
            openerp.product_variant_multi[files[i]](instance);
        }
    }
};
