# -*- encoding: utf-8 -*-

from osv import fields, osv
import netsvc
import decimal_precision as dp
from tools.translate import _
import time
import re

# ASavchenko
# Unknown non-using model ??? May be rest from v.6.0.3

#class sale_order_multiple_products(osv.osv):
#	_name = 'sale.order.multiple.products'
#	
#	def product_id_change(self, cr, uid, ids, product_id, product_uom, product_uom_qty, context=None):
#		
#		sale_order_obj=self.browse(cr, uid, ids[0], context=context).sale_order_id
#		pricelist=sale_order_obj.pricelist_id.id
#		
#		sale_order_line=self.pool.get('sale.order.line')
#		ret = sale_order_line.product_id_change(cr, uid, [], pricelist,
#			 product_id, qty=product_uom_qty, uos=product_uom,
#			 partner_id=sale_order_obj.partner_id.id, date_order=sale_order_obj.date_order,
#			 context=context)
#		return ret
#	
#	def product_uom_change(self, cr, uid, ids, product_id, product_uom, product_uom_qty, context=None):
#		ret=self.product_id_change(cr, uid, ids, product_id, product_uom, product_uom_qty, context=None)
#		if 'product_uom' in ret['value']:
#			del ret['value']['product_uom']
#		if not product_uom:
#			ret['value']['price_unit'] = 0.0
#		return ret
#			
#	def product_packaging_change(self, cr, uid, ids, product_id, product_uom, product_uom_qty, packaging, context=None):
#		sale_order_line=self.pool.get('sale.order.line')
#		
#		sale_order_obj=self.browse(cr, uid, ids[0], context=context).sale_order_id
#		pricelist=sale_order_obj.pricelist_id.id
#		
#		ret=sale_order_line.product_packaging_change(cr, uid, ids, pricelist, product_id, qty=product_uom_qty, uom=product_uom,
#                               partner_id=sale_order_obj.partner_id.id, packaging=packaging, flag=True, context=context)
#		return ret
#	
#sale_order_multiple_products()


class sale_order_multiple(osv.osv):
    
    _inherit = 'sale.order'
    _name = 'sale.order'
    _columns = {
		'tmpl_id': fields.dummy(string='Template', relation='product.template', type='many2one'),
		#'multi': fields.dummy(string='Multi fields'),
    }
    
    def get_default_values(self, cr, uid, form_values, related_field, view_name=None):
    	sale_order_line_obj = self.pool.get('sale.order.line')
    	try:
    		pricelist_id = form_values['pricelist_id']
    		product_id = form_values['product_id']
    		count_products = form_values['count_products']
    		partner_id = form_values['partner_id']
    	except KeyError:
    		raise osv.except_osv('Not enough data for calculate values')
    	
    	defaults = sale_order_line_obj.product_id_change(cr, uid, [], pricelist_id, product_id, qty=count_products,
            uom=False, qty_uos=0, uos=False, name='', partner_id=partner_id,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None)
        
        if not defaults or 'value' not in defaults:
        	raise osv.except_osv('Error in calculation default values')
        
        defaults['value']['product_uom_qty'] = form_values['count_products']
        parameters_values = self.pool.get('product.product').browse(cr, uid, product_id).parameters_values
        defaults['value']['name'] += ' ' + parameters_values
        
        return defaults['value']
	
#    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
#        fields=super(sale_order_multiple, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
#        
#        if view_type == 'form' and 'tmpl_id' in fields['fields']:
#	        tmpl_ids = self.pool.get('product.template').search(cr, uid, [], context=context)
#	        templates = self.pool.get('product.template').browse(cr, uid, tmpl_ids, context=context)
#	        
#	        fields['fields']['tmpl_id']['selection'] = []
#	        
#	        for rec in templates:
#	        	fields['fields']['tmpl_id']['selection'].append((rec.id, rec.name))
#        
#        return fields       
            
sale_order_multiple()

class purchase_order_multiple(osv.osv):
    _inherit = 'purchase.order'
    _name = 'purchase.order'
    _columns = {
    	'tmpl_id': fields.dummy(string='Template', relation='product.template', type='many2one'),
        # Darya Ambrazhevich wants to make this field mandatory....why not
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
    }
    
    def get_default_values(self, cr, uid, form_values, related_field, view_name=None):
        """
        Hook-function to get default values for order_line
        @param obj: psycopg2 cursor
        @param int: user ID
        @param dict: values from form to calculate
        @param dict: None
        """
        
        order_line_obj = self.pool.get('purchase.order.line')
        try:
        	pricelist_id = form_values['pricelist_id']
        	product_id = form_values['product_id']
        	count_products = form_values['count_products']
        	partner_id = form_values['partner_id']
        	date_order = form_values['date_order']
        except KeyError:
        	raise osv.except_osv('Not enough data for calculate values')
        
        defaults = order_line_obj.onchange_product_id(cr, uid, [], pricelist_id, product_id, qty=count_products,
        	uom_id=False, partner_id=partner_id, date_order=date_order, fiscal_position_id=False, 
        	date_planned=False, name=False, notes=False, context=None)
        ret = defaults['value']
        
        product = self.pool.get('product.product').browse(cr, uid, product_id)
        parameters_values = product.parameters_values
        ret['name'] += ' ' + parameters_values
        if not defaults or 'value' not in defaults:
        	raise osv.except_osv('Error in calculation default values')
        
        params = {}#{'template_id': product.product_tmpl_id.id}
        for param in product.dimension_value_ids:
            params[param.dimension_id.description] = param.option_id.name
        ret.update(params)
        
        return ret

		
purchase_order_multiple()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'
    
    _columns = {
    	'parameters_values': fields.related('product_id', 'parameters_values', type='char', size=128, store=False, string="Значения параметров"),
        'params': fields.dummy('Multi fields'),
    }
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(purchase_order_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        arch = ''
    
        # Add columns with product's parameters
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
        types = type_obj.browse(cr, uid, types)
        
        for type in types:
            fields['fields'].update({type.description: {
                                                 'type': 'char',
                                                 'select': True,
                                                 'selectable': True,
                                                 'string': type.name,
                                                 'size': 64,
                                                 }})
            arch += '<field name="%s" />' % type.description
        
        fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
        
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        
        ret = super(purchase_order_line, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
    
        param_fields = []
        if fields and 'product_id' in fields:
            for type in type_obj.browse(cr, uid, types):
                if type.description in fields:
                    param_fields.append(type.description)
        
            product_ids = [item['product_id'] for item in ret]
            product_ids = [i[0] if isinstance(i, tuple) else i for i in product_ids]
            ff = []
            for i, item in enumerate(product_ids):
                if not item:
                    ff.append(i)
            ff.reverse()
            for i in ff:
                del(product_ids[i])
                        
            if param_fields:
                for product in self.pool.get('product.product').browse(cr, uid, product_ids):
                    ind = False
                    for i, item in enumerate(product_ids):
                        if item == product.id:
                            ind = i
                            break
                    
                    for param_value in product.dimension_value_ids:
                        if param_value.dimension_id.show_in_tree and param_value.dimension_id.description in param_fields:   
                            ret[ind].update({param_value.dimension_id.description: param_value.option_id.name})
        
        time2 = time.time()
        if (time2-time1) > 1:
            print "Time for showing parameters - %s" % round(time2-time1)
        return ret
    
purchase_order_line()

class sale_order_line(osv.osv):
	_name = 'sale.order.line'
	_inherit = 'sale.order.line'

	_columns = {
		'parameters_values': fields.related('product_id', 'parameters_values', type='char', size=128, store=False, string="Значения параметров")
	}
sale_order_line()
