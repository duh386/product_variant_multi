# -*- coding: utf-8 -*-

from osv import fields, osv
import re
from tools.translate import _

class detail_product_production(osv.osv_memory):
    _name = 'detail.product.production'
    _description = 'Detailing product from template in mrp.production view'
    
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields=super(detail_product_production, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
    
        if 'active_id' in context and 'active_model' in context:
            if context['active_model'] == 'mrp.production.product.line':
                tmpl_id = self.pool.get('mrp.production.product.line').\
                    browse(cr, uid, context['active_id']).template_id.id
            elif context['active_model'] == 'mrp.production':
                tmpl_id = self.pool.get('mrp.production').\
                    browse(cr, uid, context['active_id']).template_id.id
            else:
                return fields
        else:
            return fields

        query="""
                SELECT dv.dimension_id, dv.option_id, dt.name as type_name, dop.name as option_name 
                FROM product_variant_dimension_value as dv
                LEFT JOIN product_variant_dimension_type as dt ON dt.id=dv.dimension_id
                LEFT JOIN product_variant_dimension_option as dop ON dop.id=dv.option_id
                WHERE dv.product_tmpl_id=%s
                ORDER BY dt.sequence
            """ % tmpl_id
        cr.execute(query)
        multi_fields=cr.fetchall()
        multi_types={}
        multi_types_str=''
        # Add variant fields
        if multi_fields:
            for row in multi_fields:
                # 0 - type_id, 1 - option_id, 2 - type_name, 3 - option_name
                field_name='product_tmpl_id_'+str(row[0])
                if field_name not in multi_types:
                    multi_types[field_name]={
                        'context': {},
                        'domain': [],
                        'relation': 'product.variant.dimension.option',
                        'required': True,
                        'selectable': True,
                        'selection': [(row[1], row[3])],
                        'string': row[2],
                        'type': 'many2one',
                        'views': {},
                    }
                    multi_types_str+='<newline /><field name="%s" widget="selection" required="1" />' % field_name 
                else:
                    multi_types[field_name]['selection'].append((row[1], row[3]))
            for key, val in multi_types.items():
                fields['fields'][key]=val
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', multi_types_str, fields['arch'])
        else:
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '    ', fields['arch'])
                
        # Add all template variants for widget SelectionCreateProduct
        if view_type == 'form':
            tmpl_ids = self.pool.get('product.template').search(cr, uid, [], context=context)
            templates = self.pool.get('product.template').browse(cr, uid, tmpl_ids, context=context)
            
            fields['fields']['tmpl_id']['selection'] = []
            
            for rec in templates:
                fields['fields']['tmpl_id']['selection'].append((rec.id, rec.name))
        
        return fields
    
    def _get_tmpl_id(self,cr, uid, ctx):
        if 'active_id' in ctx and 'active_model' in ctx:
            if self._name == ctx['active_model']:
                line=self.browse(cr, uid, ctx['active_id'])
                tmpl_id = line.tmpl_id.id
            else:
                if ctx['active_model'] == 'mrp.production.product.line' or ctx['active_model'] == 'mrp.production':
                    tmpl_id = self.pool.get(ctx['active_model']).\
                    browse(cr, uid, ctx['active_id']).template_id.id
                    return tmpl_id
                else:
                    return False
        else:
            return False
    
    _columns = {
        'tmpl_id': fields.many2one('product.template', 'Template', readonly=False),
        'multi': fields.dummy(string='Multi fields'),
        'multi_values': fields.text('Multi values', translate=False, required=False),
    }
    
    _defaults = {
        'tmpl_id': _get_tmpl_id
    }
    
    def choose_product(self, cr, uid, ids, context=None):
        
        vals = eval(self.browse(cr, uid, ids[0], context=context).multi_values)
        for key, val in vals.items():
            if key.startswith('product_tmpl_id_') and not val:
                raise osv.except_osv('Warning', _('Fill all characteristics'))
        
        product_id = self.pool.get('product.product').create_product_from_parameters(cr, uid, vals, context=context)
        if product_id:
            self.unlink(cr, uid, ids, context=context)
        
        if 'active_id' not in context:
            raise osv.except_osv('Error', 'Wrong context data')
        if context['active_model'] == 'mrp.production.product.line':
            self.pool.get('mrp.production.product.line').write(cr, uid, context['active_id'], {'product_id': product_id})
        elif context['active_model'] == 'mrp.production':
            self.pool.get('mrp.production').write(cr, uid, context['active_id'], {'product_id': product_id})
        else:
            raise osv.except_osv('Error', 'Wrong model')

        return {}
    
    def create(self, cr, uid, vals, context=None):
        vals['multi_values'] = str(vals)
        create_id = super(detail_product_production, self).create(cr, uid, vals, context=context)
        return create_id

    
    def write(self, cr, uid, ids, vals, context=None):
        multi_values = self.browse(cr, uid, ids[0]).multi_values
        multi_values = eval(multi_values)
        for key, val in vals.items():
            multi_values[key] = val
        
        vals['multi_values'] = str(multi_values)
        super(detail_product_production, self).write(cr, uid, ids, vals, context=context)
        return True
    

#    def do_refresh_view(self, cr, uid, ids, context):
#        
#        line=self.browse(cr, uid, ids)[0]
#        if not line:
#            return dict(error=_('Wrong data'))
#        
#        return {
#            'domain': "[]",
#            'name': 'Задать продукт по шаблону',
#            'view_type': 'form',
#            'view_mode': 'form',
#            'res_model': 'detail.product.production',
#            'view_id': False,
#            'context': {},
#            'type': 'ir.actions.act_window',
#            'target': 'new',
#        }

detail_product_production()