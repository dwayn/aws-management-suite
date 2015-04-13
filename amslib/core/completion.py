from amslib.core.manager import BaseManager



class ArgumentCompletion(BaseManager):

    def _general_db_completion(self, table, column, need_distinct=True, filters={}):
        rval = []
        distinct = ''
        if need_distinct:
            distinct = 'distinct'
        sql = "select {0} {1} from {2} ".format(distinct, column, table)
        vals = []
        wheres = []
        if filters:
            for k,v in filters.iteritems():
                wheres.append("{0}=%s".format(k))
                vals.append(v)

        if wheres:
            sql += " where "
            sql += " and ".join(wheres)
        self.db.execute(sql, vals)
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                if row[0]:
                    rval.append(row[0])
        return rval



    def security_group_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'security_group_id', False, filters)


    def security_group_vpc(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'vpc_id', True, filters)


    def security_group_name(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'name', False)


    def region(self, **kwargs):
        return self._general_db_completion('availability_zones', 'region', True)

    def availability_zone(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        return self._general_db_completion('availability_zones', 'availability_zone', False, filters)

    def instance_id(self, **kwargs):
        return self._general_db_completion('hosts', 'instance_id', False)

    def ami_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('amis', 'ami_id', False, filters)

    def vpc_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('vpcs', 'vpc_id', False, filters)

    def subnet_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            filters['availability_zone'] = kwargs['parsed_args'].zone
        return self._general_db_completion('subnets', 'subnet_id', False, filters)

    def keypair(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('key_pairs', 'key_name', False, filters)

    def __region_from_az(self, az):
        self.db.execute("select region from availability_zones where availability_zone = %s", (az,))
        row = self.db.fetchone()
        if not row:
            return None
        return row[0]

    def config_value(self, **kwargs):
        if 'parsed_args' in kwargs and 'name' in kwargs['parsed_args'] and kwargs['parsed_args'].name:
            self.db.execute("select `type`,`value` from config where `var`=%s and configurable=1",(kwargs['parsed_args'].name, ))
            row = self.db.fetchone()
            if row:
                if row[0] == 'bool':
                    return ['0', '1']
                else:
                    return [row[1]]
        return None

    def config_name(self, **kwargs):
        filters = {'configurable': 1}
        return self._general_db_completion('config', '`var`', False, filters)