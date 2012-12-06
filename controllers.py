# -*- coding: utf-8 -*-
try:
    import openerp.addons.web.common.http as openerpweb
except ImportError:
    import web.common.http as openerpweb

class Widgets(openerpweb.Controller):
    _cp_path = '/product_variant_multi/widgets'
   
    @openerpweb.jsonrequest
    def get_default_data(self, request, template_id, data, model, args, related_field, view_name=None):
        """
        Return default values for choosen relate one2many
        @param <obj>: describe HTTP request
        @param <int>: template ID
        @param <dict>: values of multi characteristics
        @param <dict>: current form values
        """

        # Get product by characteristics
        product_obj = request.session.model('product.product')
        template_obj = request.session.model('product.template')
        
        ctx = request.context
        template = template_obj.read(template_id, ['is_multi_variants'], context=ctx)

        data = dict([(key.replace('dim_', ''), val) for key, val in data.items()])
        
        # Creating new product or find existing
        vals = {}
        for key, val in data.iteritems():
            vals['product_tmpl_id_'+str(key)] = val
        vals['tmpl_id'] = template_id
        product_id = product_obj.create_product_from_parameters(vals=vals)
            
        args['product_id'] = product_id
        model = request.session.model(model)
        
        #Call hook-function for each model
        try:
            defaults = model.get_default_values(args, related_field, view_name)
        except Exception, e:
            return {'error': u'Неверная функция для определения значений.'}
        defaults['product_id'] = product_id

        return defaults
    
    @openerpweb.jsonrequest
    def get_all_templates(self, request):
        """Get list of all templates
        @param request <obj>
        @return <list>: example - [{'id': tpl_id1, 'name': 'tpl_name1'},....]
        """
        template_obj = request.session.model('product.template')
        ids = template_obj.search([])
        tpls = template_obj.read(ids, ['name'])
        return tpls
            