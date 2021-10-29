import os
from sqlite3.dbapi2 import Cursor
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, g
from flask.helpers import flash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from db import get_db
import datetime
import functools
from wtforms import Form, BooleanField, StringField, PasswordField, SelectField, validators
from wtforms.fields.simple import SubmitField
from wtforms.validators import Required
from werkzeug.security import generate_password_hash, check_password_hash 
import sqlite3

UPLOAD_FOLDER = 'static/img'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
Bootstrap(app)

app.secret_key = 'hWdsd39lg'

# --------------------------- FORMS --------------------------- #


class LoginForm(FlaskForm):
    email = StringField('Ingresar usuario', validators=[Required("Campo necesario.")])
    password = PasswordField('Ingresar contraseña', validators=[Required("Campo necesario.")])
    remember = BooleanField('Recordar Inicio de sesión')
    submit = SubmitField('INICIAR SESIÓN')

class RegisterForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[Required("Campo necesario.")])
    email = StringField('Email', validators=[Required("Campo necesario.")])
    password = PasswordField('Contrasena', validators=[Required("Campo necesario.")])
    confirm_password = PasswordField('Confirmar Contrasena', validators=[Required("Campo necesario.")])
    birth_day = SelectField('Dia', choices= ['Seleccione'] + list(range(1, 32)), validators=[Required("Campo necesario.")])
    birth_month = SelectField('Mes', choices=['Seleccione','01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'], validators=[Required("Campo necesario.")])
    birth_year = SelectField('Año', choices= ['Seleccione'] + list(range(1940,2021)), validators=[Required("Campo necesario.")])
    select_sex = SelectField('Sexo', choices=['Seleccione','Masculino', 'Femenino', 'No binario'], validators=[Required("Campo necesario.")])
    submit = SubmitField('Confirmar Registro')


# --------------------------- ROUTES --------------------------- #

def login_required(view):
    @functools.wraps( view ) # toma una función utilizada en un decorador y añadir la funcionalidad de copiar el nombre de la función.
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect( url_for( 'login' ) ) # si no tiene datos, lo envío a que se loguee
        return view( **kwargs )
    return wrapped_view

def admin_required(view):
    @functools.wraps( view ) # toma una función utilizada en un decorador y añadir la funcionalidad de copiar el nombre de la función.
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('home'))
        if g.user[6]!=1 and g.user[6]!=2:
            return redirect( url_for( 'home' ) ) # si no tiene datos, lo envío a que se loguee
        return view( **kwargs )
    return wrapped_view

def super_required(view):
    @functools.wraps( view ) # toma una función utilizada en un decorador y añadir la funcionalidad de copiar el nombre de la función.
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('home'))
        if g.user[6]!=1:
            return redirect( url_for( 'home' ) ) # si no tiene datos, lo envío a que se loguee
        return view( **kwargs )
    return wrapped_view


#INDEX
@app.route('/', methods=["POST", "GET"])
def home():
    get_db()
    db=get_db()
    result=db.execute("SELECT codigo,nombre,descripcion,genero,clasificacion,duracion,director,codigo,idioma,calificacion,portada from funcion inner join pelicula ON  pelicula.codigo = funcion.pelicula_codigo group by pelicula_codigo")
    result= result.fetchall()
    
    pronto=db.execute("SELECT pelicula.*  FROM pelicula WHERE NOT EXISTS (SELECT * FROM funcion WHERE pelicula.codigo=funcion.pelicula_codigo)")
    pronto= pronto.fetchall()
    
    movie_names = [movie_name[1] for movie_name in result]
    if request.method == 'POST':
        nombre = request.form['movie_name']
        movie_id=db.execute("SELECT codigo FROM pelicula WHERE nombre=?",(nombre,))
        movie_id= movie_id.fetchall()
        return redirect(url_for('show_movie', movie=movie_id[0][0]))
    
    return render_template('index.html',result=result, movie_names=movie_names, pronto=pronto)

#LOGIN
@app.route('/login/', methods=['POST', 'GET'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        # autenticacion
        password = request.form['password']
        email = request.form['email']
        error = None
        
        db = get_db()
        
        if not email:
            error = "username requerido."
            flash( error )
        if not password:
            error = "Contraseña requerida."
            flash( error )

        if error is not None:
            # SI HAY ERROR:
            return render_template("login.html", form=login_form)
        else:
            # No hay error:
            user = db.execute(
                'SELECT id, email, password FROM usuario WHERE email = ?'
                ,
                (email,)
            ).fetchone() 
            print(user)  

            if user is None:
                error = "username no existe." # Pendiente por seguridad modificar el mensaje
                flash(error)
            else:                
                username_valido = check_password_hash(user[2], password)
                if not username_valido:
                    error = "username y/o contraseña no son correctos."
                    flash( error )                
                    return render_template("login.html", form=login_form)
                else: 
                    session.clear()
                    session['id_usuario'] = user[0] # con esto estoy guardando el id_usuario logueado

                    #Modifica la función login para que cuando confirme la sesión, cree una cookie
                    #del tipo ‘username’ y almacene el username.
                    response = make_response( redirect( url_for('home') ) )
                    response.set_cookie( 'username', email  ) # nombre de la cookie y su valor
                    
                    return response
        # if g.user[6]==1 or g.user[6]==2:
        #     return redirect(url_for('manage_movies'))
        # else:
        #     return redirect(url_for('home'))
    
    return render_template('login.html', form=login_form)

@app.before_request
def cargar_usuario_registrado():
    # g.user = con los datos de la base de datos, basados en la session.
    id_usuario = session.get('id_usuario')
    if id_usuario is None:
        g.user = None
    else:
        g.user = get_db().execute(
                'SELECT id, nombre, email, password,fecha_nacimiento,genero,cargo_id FROM usuario WHERE id = ?'
                ,
                (id_usuario,)
            ).fetchone()


#REGISTER
@app.route('/registro/', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']            
        confirm_password = request.form['confirm_password']
        birth_day = request.form['birth_day']
        birth_month = request.form['birth_month']
        birth_year = request.form['birth_year']
        select_sex = request.form['select_sex']
        fecha_naciemiento=birth_year+"-"+birth_month+"-"+birth_day
        error = None
        db = get_db()
        
        if not username:
            error = "Usuario requerido."
            flash(error)
        if not password:
            error = "Contraseña requerida."
            flash(error)
        
        ## Buscar correo y verificar si ya existe https://www.youtube.com/embed/VzuEMvd0QWI   
        user_email = db.execute(
            'SELECT * FROM usuario WHERE email = ?'
            ,
            (email,)
        ).fetchone()            
        if user_email is not None:
            error = "Correo ingresado ya existe."
            flash(error)
            register_form = RegisterForm()
            return render_template('register.html',register_form=register_form, error=error)
        else:
            #Seguro:
            password_cifrado = generate_password_hash(password)
            db.execute(
                'INSERT INTO usuario (nombre,email,password,fecha_nacimiento,genero,cargo_id) VALUES (?,?,?,?,?,?) '
                ,
                (username,email,password_cifrado,fecha_naciemiento,select_sex,3)
            )
                    
            db.commit()
            
            flash('Revisa tu correo para activar tu cuenta')
            
            return redirect( url_for( 'login' ) )

    register_form = RegisterForm()
    return render_template('register.html', register_form=register_form)




# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect( url_for( 'home' ) )


#PROFILE_USER
@app.route('/perfil/', methods=['POST','GET'])
def show_user_profile():
    if request.method == 'POST':
        db=get_db()
        id = request.form['id']
        name = request.form['name']
        email = request.form['email']
        genero = request.form['genero']
        date = request.form['date']
        ## Buscar correo y verificar si ya existe    
        user_email = db.execute(
            'SELECT * FROM usuario WHERE email = ?'
            ,
            (email,)
        ).fetchone()            
        if user_email is not None and g.user[0]!=user_email[0]:
            error = "Correo ingresado ya existe."
            flash(error)
            return redirect (url_for('show_user_profile'))
        else:
            #Seguro:
            sql="UPDATE usuario SET nombre='{}',email='{}',fecha_nacimiento='{}',genero='{}' WHERE id= '{}'".format(name,email,date,genero,id)
            db.execute(sql)
            db.commit()
            flash('Datos actualizados')
            
            return redirect (url_for('show_user_profile'))
            
    if g.user[6]==1 or g.user[6]==2:
            return redirect(url_for('manage_movies'))
    else:
        return render_template('perfil_user.html')

#BUSCAR
@app.route('/buscar/<string:movie_name>', methods=['GET'])
def search(movie_name=None):
    return render_template('buscar.html', movie_name=movie_name)

#MOVIE DETAILS
@app.route('/watch/<string:movie>', methods=['GET', 'POST'])
def show_movie(movie):
    
    db=get_db()
    result=db.execute("SELECT * FROM pelicula ")
    result= result.fetchall()

    funcion=db.execute("SELECT * FROM funcion where pelicula_codigo =?", (movie,))
    funcion= funcion.fetchall()
    print(funcion)
    
    
    movie_names = [movie_name[1] for movie_name in result]
    if request.method == 'POST' and request.form['movie_name']:
        nombre = request.form['movie_name']
        movie_id=db.execute("SELECT codigo FROM pelicula WHERE nombre=?",(nombre,))
        movie_id= movie_id.fetchall()
        return redirect(url_for('show_movie', movie=movie_id[0][0]))
 
    codigo=comment=movie
    movie=db.execute("SELECT * FROM pelicula WHERE codigo=?",(movie,))
    movie= movie.fetchall()
    comment=db.execute("SELECT contenido,fecha,nombre FROM comentario inner join usuario ON usuario.id=comentario.usuario_id  where pelicula_codigo=?",(comment,))
    comment= comment.fetchall()
    score=db.execute("SELECT score FROM calificacion inner join pelicula ON pelicula.codigo=calificacion.pelicula_id  where pelicula_id=?",(codigo,))
    score= score.fetchall()

    if sum([int(x[0]) for x in score]) > 0:
        avg_score = sum([int(x[0]) for x in score])/len(score)
        return render_template('movie_detailed.html', movie=movie,comment=comment,pelicula=codigo, score=avg_score, total_votos=len(score), funcion=funcion)

    
    print("g.user:" ,g.user)
    
    if request.method == 'POST' and g.user is not None:
        stars =request.form['rate-movie']
        movie_id = request.form['id']
        print("codigo: ", codigo)
        print("movie_id: ", movie_id)
        if g.user:
            user_vote = db.execute("SELECT id_calificacion, usuario_id, score FROM calificacion inner join pelicula ON pelicula.codigo=calificacion.pelicula_id  where pelicula_id=? and usuario_id=?", (movie_id, g.user[0]))
            user_vote= user_vote.fetchall()
            print(user_vote)
            if user_vote:
                sql="UPDATE calificacion SET score= '{}' WHERE id_calificacion= '{}'".format(stars, user_vote[0][0])
                db.execute(sql)
                db.commit()
            else:
                db.execute("INSERT INTO calificacion (score, usuario_id, pelicula_id) VALUES (?,?,?) "
                            , (stars,g.user[0],movie_id) )
                db.commit()
            # db.close()
        return redirect(url_for( 'show_movie',movie=movie_id))

    
    db.close()
    return render_template('movie_detailed.html', movie=movie,comment=comment,pelicula=codigo, movie_names=movie_names, funcion=funcion)

#PRONTO
@app.route('/pronto/', methods=['GET','POST'])
def upcoming_movies():
    get_db()
    db=get_db()
    result=db.execute("SELECT * FROM pelicula")
    result= result.fetchall()
    pronto=db.execute("SELECT pelicula.*  FROM pelicula WHERE NOT EXISTS (SELECT * FROM funcion WHERE pelicula.codigo=funcion.pelicula_codigo)")
    pronto= pronto.fetchall()

    movie_names = [movie_name[1] for movie_name in result]
    
    if request.method == 'POST':
        nombre = request.form['movie_name']
        movie_id=db.execute("SELECT codigo FROM pelicula WHERE nombre=?",(nombre,))
        movie_id= movie_id.fetchall()
        db.close()
        return redirect(url_for('show_movie', movie=movie_id[0][0]))
    
    return render_template('pronto.html', movie_names= movie_names, pronto=pronto)

#FUNCIONES ADMIN

@app.route('/admin_funciones/', methods=['GET', 'POST'])
def manage_functions():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        db=get_db()
        result=db.execute("SELECT id,categoria,sala,hora1,hora2,hora3,precio,codigo,nombre FROM funcion inner join pelicula ON funcion.pelicula_codigo=pelicula.codigo")
        result= result.fetchall()
        db.close()
    return render_template('funciones.html',result=result)

#PELICULAS ADMIN

@app.route('/admin_peliculas/', methods=['GET', 'POST'])
def manage_movies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        db=get_db()
        result=db.execute("SELECT * FROM pelicula")
            
        result= result.fetchall()
        db.close()
        return render_template('peliculas.html',result=result)

#ROL Y USER ADMIN

@app.route('/admin_user/', methods=['GET', 'POST'])
def manage_users():
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    try:
        if request.method == 'GET':
            db=get_db()
            result=db.execute("SELECT * FROM usuario INNER JOIN cargo ON usuario.cargo_id = cargo.id")
            
            result= result.fetchall()
            db.close()
            return render_template('rolyuser.html',result=result)    
    except:
        return render_template('rolyuser.html')

@app.route('/admin_user/delete', methods=['GET', 'POST'])
def deleteusers():
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        id=request.args.get('id')
        db=get_db()
        db.execute("DELETE FROM usuario WHERE id=?",(id,))
        db.commit()
        db.close()
    return redirect(url_for('manage_users'))    
  
@app.route('/admin_user/edit', methods=['GET', 'POST'])
def editusers():
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        id=request.args.get('id')
        db=get_db()
        result=db.execute("SELECT usuario.id,nombre,email,fecha_nacimiento,genero,cargo_id,cargouser FROM usuario INNER JOIN cargo ON usuario.cargo_id = cargo.id WHERE usuario.id=?",(id,))
        result= result.fetchall()
        db.close()
    return render_template('edituser.html',result=result)    

@app.route('/admin_user/see', methods=['GET', 'POST'])
def seeusers():
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        id=request.args.get('id')
        db=get_db()
        result=db.execute("SELECT usuario.id,nombre,email,fecha_nacimiento,genero,cargo_id,cargouser FROM usuario INNER JOIN cargo ON usuario.cargo_id = cargo.id WHERE usuario.id=?",(id,))
        result= result.fetchall()
        db.close()
    return render_template('seeusers.html',result=result) 

@app.route('/admin_user/save/', methods=['GET', 'POST'])
def usersave():
    if request.method == 'POST':   
        id = request.form['id']
        cargo =request.form['cargo']
        db=get_db()
        sql="UPDATE usuario SET cargo_id= '{}' WHERE id= '{}'".format(cargo,id)
        db.execute(sql)
        db.commit()
        db.close()
        return redirect(url_for( 'manage_users'))


#crear peliculas        

@app.route('/admin_peliculas/crear/', methods=['GET', 'POST'])
def create_movies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'POST':
        pass
    return render_template('createmovies.html')

def allowed_file(filename):
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

          
@app.route('/admin_peliculas/save/', methods=['GET', 'POST'])
def save_movies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'POST':   
        nombre = request.form['titulo']
        genero = request.form['genero']            
        descrip = request.form['descrip']
        clasificacion = request.form['clasificacion']
        duracion = request.form['duracion']
        director = request.form['director']
        cast = request.form['cast']
        idioma = request.form['idioma']
        file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            portada="/static/img/"+filename
            #return redirect(url_for('download_file', name=filename))


        db=get_db()
        db.execute('INSERT INTO pelicula (nombre,descripcion,genero,clasificacion,duracion,director,cast,idioma,calificacion,portada) VALUES (?,?,?,?,?,?,?,?,?,?) '
                ,
                (nombre,descrip,genero,clasificacion,duracion,director,cast,idioma,0,portada))

        db.commit()
        db.close()  
        return redirect(url_for( 'manage_movies')) 


@app.route('/admin_peliculas/ver/', methods=['GET', 'POST'])
def seemovies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        
        codigo=request.args.get('codigo')
        db=get_db()
        result=db.execute("SELECT * FROM pelicula WHERE codigo=?",(codigo,))
        result= result.fetchall()
        db.close()
        return render_template('seemovies.html',result=result)


@app.route('/admin_peliculas/edit/', methods=['GET', 'POST'])
def editmovies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        codigo=request.args.get('codigo')
        db=get_db()
        result=db.execute("SELECT * FROM pelicula WHERE codigo=?",(codigo,))
        result= result.fetchall()
        db.close()
        return render_template('editmovies.html',result=result)


@app.route('/admin_peliculas/update/', methods=['GET', 'POST','PUT'])
def updatemovies():
    
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'POST':
        nombre = request.form['nombre']
        genero = request.form['genero']            
        descrip = request.form['descrip']
        clasificacion = request.form['clasificacion']
        duracion = request.form['duracion']
        director = request.form['director']
        cast = request.form['cast']
        idioma = request.form['idioma']
        codigo = request.form['codigo']

    db=get_db()
    #"UPDATE Producto  SET nombre = '{}', precio = '{}', existencia = '{}' WHERE id = '{}'".format(nombre, precio, existencia, id)
    sql="UPDATE pelicula SET nombre='{}', descripcion= '{}', genero= '{}', clasificacion= '{}', duracion= '{}', director= '{}' ,cast= '{}', idioma= '{}' WHERE codigo= '{}'".format(nombre,descrip,genero,clasificacion,duracion,director,cast,idioma,codigo)
    db.execute(sql)
    db.commit()
    db.close()
    return redirect(url_for( 'manage_movies'))


@app.route('/admin_peliculas/delete/', methods=['GET', 'POST'])
def deletemovies():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        codigo=request.args.get('codigo')
        db=get_db()
        db.execute("DELETE FROM pelicula WHERE codigo=?",(codigo,))
        db.commit()
        db.close()
        return redirect(url_for( 'manage_movies')) 

#crear funcion    
 
@app.route('/admin_funciones/crear/', methods=['GET', 'POST'])
def create_funcion():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        db=get_db()
        result=db.execute("SELECT codigo,nombre FROM pelicula")            
        result= result.fetchall()
        db.close()
        
    return render_template('createfuncion.html',result=result)


@app.route('/admin_funciones/save/', methods=['GET', 'POST'])
def save_funcion():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'POST':   
        categoria = request.form['categoria']
        sala = request.form['sala']            
        hora1 = request.form['hora1']
        hora2 = request.form['hora2']
        hora3 = request.form['hora3']
        precio = request.form['precio']
        pelicula_codigo = request.form['pelicula_codigo']
        
        db=get_db()
        db.execute('INSERT INTO funcion (categoria,sala,hora1,hora2,hora3,puntuacion,precio,pelicula_codigo) VALUES (?,?,?,?,?,?,?,?) '
                ,
                (categoria,sala,hora1,hora2,hora3,0,precio,pelicula_codigo))

        db.commit()
        db.close()  
        return redirect(url_for( 'manage_functions'))


@app.route('/admin_funciones/edit/', methods=['GET', 'POST'])
def editfuncion():
    if request.method == 'GET':
        id=request.args.get('id')
        db=get_db()
        result=db.execute("SELECT * FROM funcion WHERE id=?",(id,))
        result= result.fetchall()
        db.close()
        return render_template('editfuncion.html',result=result)


@app.route('/admin_funciones/update/', methods=['GET', 'POST','PUT'])
def updatefuncion():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'POST':
        id = request.form['id']
        categoria = request.form['categoria']
        sala = request.form['sala']            
        hora1 = request.form['hora1']
        hora2 = request.form['hora2']
        hora3 = request.form['hora3']
        precio = request.form['precio']
        pelicula_codigo = request.form['pelicula_codigo']
  
    db=get_db()
    #"UPDATE Producto  SET ca = '{}', precio = '{}', existencia = '{}' WHERE id = '{}'".format(nombre, precio, existencia, id)
    sql="UPDATE funcion SET categoria='{}', sala= '{}', hora1= '{}', hora2= '{}', hora3= '{}', precio= '{}', pelicula_codigo= '{}' WHERE id= '{}'".format(categoria,sala,hora1,hora2,hora3,precio,pelicula_codigo,id)
    db.execute(sql)
    db.commit()

    db.close()
    return redirect(url_for( 'manage_functions'))


@app.route('/admin_funciones/ver/', methods=['GET', 'POST'])
def seefuncion():
    if request.method == 'GET':
        
        id=request.args.get('id')
        db=get_db()
        result=db.execute("SELECT * FROM funcion WHERE id=?",(id,))
        result= result.fetchall()
        db.close()
        return render_template('seefuncion.html',result=result)


@app.route('/admin_funciones/delete/', methods=['GET', 'POST'])
def deletefuncion():
    if g.user is None:
        return redirect(url_for('home'))
    if g.user[6]!=1 and g.user[6]!=2:
        return redirect(url_for('home'))
    if request.method == 'GET':
        id=request.args.get('id')
        db=get_db()
        db.execute("DELETE FROM funcion WHERE id=?",(id,))
        db.commit()
        db.close()
        return redirect(url_for( 'manage_functions')) 

@login_required
@app.route('/watch/comment', methods=['GET', 'POST'])
def createcomment():
    x = datetime.datetime.now()

    day = x.strftime("%d")
    month = x.strftime("%b")
    year = x.strftime("%Y")
    hour = x.strftime("%X")

    date = f"{day}-{month}-{year} {hour}"
    if request.method == 'POST':
        user=request.form['user']
        comment=request.form['comment']
        pelicula=request.form['pelicula']
        if g.user:
            db=get_db()
            db.execute("INSERT INTO comentario (contenido,fecha,pelicula_codigo,usuario_id) VALUES (?,?,?,?) "
                        , (comment,date,pelicula,user) )
            db.commit()
            db.close()
        return redirect(url_for( 'show_movie',movie=pelicula))

@app.route('/perfil/mycomments', methods=['GET', 'POST'])
def mycomments():
    get_db()
    db=get_db()   
    comment=db.execute("SELECT idcomentario,contenido,fecha,nombre FROM comentario inner join usuario ON usuario.id=comentario.usuario_id  where usuario_id=?",(g.user[0],))
    comment= comment.fetchall()

    if request.method == 'GET' :
        id=request.args.get('id')
        modo=request.args.get('modo')
        if modo=='d':
            db.execute("DELETE FROM comentario WHERE idcomentario=?",(id,))
            db.commit()
            return redirect (url_for('mycomments'))

    
    
    if request.method == 'POST':
        comment = request.form['ecomment']
        idcomentario = request.form['idcomentario']
        sql="UPDATE comentario SET contenido='{}' WHERE idcomentario= '{}'".format(comment,idcomentario)
        db.execute(sql)
        db.commit()
        return redirect (url_for('mycomments'))
    db.close()
    return render_template('mycomment.html',comment=comment)

