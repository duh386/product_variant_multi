openerp.product_variant_multi.multi_template_widget = function(openerp) {
var QWeb = openerp.web.qweb,
      _t =  openerp.web._t,
     _lt = openerp.web._lt;

// Analog of standart js-operator "alert"
var eAlert = function(title, message)
{
	$('<div>' + QWeb.render('CrashManagerWarning', {error: {
		code: 200,
		data: {
			//debug: '',
			fault_code: message,
			//type: 'server_exception'
		}
	}}) + '</div>').dialog({
        title: title,
        buttons: [
            {text: _t("Ok"), click: function() { $(this).dialog("close"); }}
        ]
    });
}

openerp.web.form.widgets.map['multi_template'] = 'openerp.web.form.MultiTemplate';
openerp.web.page.readonly.map['multi_template'] = 'openerp.web.form.FieldChar';


openerp.web.form.MultiTemplate = openerp.web.form.Field.extend({
	template: 'MultiTemplate',
	
    init: function (view, node) {
        this._super(view, node);
        this.password = this.node.attrs.password === 'True' || this.node.attrs.password === '1';
        this.template_names = new Array();
    },
    start: function() {
    	self = this;
        this._super.apply(this, arguments);
        var to_insert;
        this.rpc('/product_variant_multi/widgets/get_all_templates', {}, function(response){
        	
        	// Get list of all templates for $.autocomplete source
        	template_names = [];
        	self.templates = {};
        	for (i in response){
        		template_names.push(response[i].name);
        		self.templates[response[i].name] = response[i].id;
        	};
        	self.$element.find('input.multi_tmpl_id').autocomplete(
    			{source: template_names,
				select: function(e, ui){
	            	// Request to controller to get parameters fields
	            	ctx = self.view.dataset.get_context();
	            	
	            	self.template_id = self.templates[ui.item.value];
	            	
	            	if (self.template_id)
	            	{
	                	if('add' in ctx)
	                        ctx.add({'template_id' : self.template_id});
	                    else
	                        ctx.template_id=self.template_id;
	                	self.rpc("/web/searchview/load", {
	                        model: 'product.product',
	                        view_id: false,
	                        context: ctx,
	                    }, function(result){
	                    	// Insert parameters of choosen templates
	                    	$('#'+self['element_id']).next().find('tbody .dimension_td').replaceWith('');
	                		to_insert = new Array();
	                		var dimensions = new Array();
	                		var fields = result.fields_view.fields;
	                		for (i in fields)
	                		{
	                			if(i.substring(0,16) == 'product_tmpl_id_')
	                			{
	                				id = i.substring(16)*1;
	                				dimensions[id] = fields[i];
	                			    var obj_to_insert = {
	                			    	id: id,
	                			    	string: fields[i]['string'],
	                			    	sequence: fields[i]['sequence']
	                			    };
	                			    obj_to_insert['options'] = new Array();
	            					var selection_len = fields[i]['selection'].length;
	                				for(var i_selection=0; i_selection < selection_len; i_selection++)
	                				{
	                					obj_to_insert['options'].push({
	                						id: fields[i]['selection'][i_selection][0],
	                						value: fields[i]['selection'][i_selection][1]
	                					});
	                				}
	                				to_insert.push(obj_to_insert);
	                			}
	                		}
	                		to_insert.sort(function(a, b){
	                			if (a.sequence == b.sequence)
	                				return 0;
	                			else if (a.sequence > b.sequence)
	                				return 1;
	                			else
	                				return -1;
	                		});
	                		$('#'+self['element_id']).next().find('tbody tr:first').prepend(QWeb.render("MultiTemplate.dimensions.labels", {dimensions: to_insert}));
	        				$('#'+self['element_id']).next().find('tbody tr:last').prepend(QWeb.render("MultiTemplate.dimensions.values", {dimensions: to_insert}));	
	        				for (i in to_insert)
	        				{
	        					var item = to_insert[i];
	        					var values = new Array();
	        					for (j in item.options){
	        						values.push(item.options[j].value);
	        					}
	        					//Set autocomplete for parameters fields
	        					$('input#dim_'+item.id).autocomplete({source: values});
	        				}
	                    
	                    });
	            	}else
	            		$('#multi_select_block > tbody .dimension_td').replaceWith('');
    			}
			});
        });
        this.$element.find('input').change(this.on_ui_change);
		
        // Set handler to button, which add item to list
        this.$element.parent().find('#button_add_multi').click(function(){
	    	var data = {};
	    	if(!self.template_id)
			{
	    		eAlert('OpenERP Warning', _t('Выберите тип продукта'));
				return false;
			}
	    	var args = {};
	    	var has_errors = false;
	    	// Validate all required form fields
	    	for(i in self.view.fields)
	    	{
	    		var field = self.view.fields[i];
	    		args[i] = field.get_value();
	    		if(!args[i] && field.required)
	    		{
	    			eAlert('OpenERP Warning', _t('Заполните '+field.string));
	    			has_errors = true;
	    			break;
	    		}
	    		if(field.name == self.node.attrs['related_field'])
	    			var temp_list = field;
	    			
	    	}
	    	if(has_errors)
	    		return;
			// Validate parameters values
			if (self.$element.find(".multi_form_dimension").length > 0)
			{
	    		var dimension_sel = true;
	        	$.each(self.$element.find(".multi_form_dimension"), function(index, value){
	        		if ($(value).val() == '')
	        		{
	        			eAlert('OpenERP Warning', _t('Заполните все характеристики'));
	        			dimension_sel = false;
	        			return false;
	        		}else{
	        			var opt_id = 'new_' + $(value).val();
	        			//Find option_id, get 'new_'+option_name if not exists
	        			for (i in to_insert){
	        				if ('dim_'+to_insert[i].id == $(value).attr('id')){
	        					for (j in to_insert[i].options){
	        						if (to_insert[i].options[j].value == $(value).val()){
	        							opt_id = to_insert[i].options[j].id;
	        							break;
	        						}
	        					}
	        					break;
	        				}
	        			}
	        			
	        			data[$(value).attr('id')] = opt_id; 
	        		}
	        	});
	        	if(!dimension_sel)
	        		return;
	    	}
	    	
	    	count_products = self.$element.find("#multi_product_qty").val()*1;
	    	if (!count_products)
	    	{
	    		eAlert('OpenERP Warning', _t('Неверное количество продукта'));
	    		return false;
	    	}
	
	    	args['count_products'] = count_products;
	    	// Get default data for list item
	    	self.rpc("/product_variant_multi/widgets/get_default_data", {
	    		template_id: self.template_id,
	    		data: data,
	    		model: self.view.model,
	    		args: args,
	    		related_field: self.node.attrs['related_field'],
	    		view_name: self.view.fields_view.name
	    	}, function(response){
	    		if(response.error)
	    		{
	    			eAlert('OpenERP Warning', response.error);
	    			return;
	    		}
	    	 	
	        	temp_list.build_domain();
	        	temp_list.build_context();
	        	
	        	response['state'] = 'draft';
	        	temp_list.dataset.create(response).then(function(r) {
					temp_list.dataset.set_ids(temp_list.dataset.ids.concat([r.result]));
					temp_list.dataset.on_change();
					
	            });
	       
	        	temp_list.reload_current_view();
	    	});
	    	document.getElementById(self.element_id).focus();
	    }).
	    keydown(function(event){
	    	if(event.which == 9)
	    	{
	    		event.preventDefault();
	    		document.getElementById(self.element_id).focus();
	    	}
	    });
        
    },
     
    set_value: function(value) {
        this._super.apply(this, arguments);
        var show_value = openerp.web.format_value(value, this, '');
        this.$element.find('input').val(show_value);
        return show_value;
    },
    update_dom: function() {
        this._super.apply(this, arguments);
        this.$element.find('input').prop('readonly', this.readonly);
    },
    set_value_from_ui: function() {
        this.value = openerp.web.parse_value(this.$element.find('input').val(), this);
        this._super();
    },
    validate: function() {
        this.invalid = false;
        try {
            var value = openerp.web.parse_value(this.$element.find('input').val(), this, '');
            this.invalid = this.required && value === '';
        } catch(e) {
            this.invalid = true;
        }
    },
    focus: function($element) {
        this._super($element || this.$element.find('input:first'));
    }
	
});

}