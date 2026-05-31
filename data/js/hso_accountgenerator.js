function accNameGen() {
  	 /*
     HSOG: Account = maxLength-8(Vorname1.Buchstabe + Nachname + **(Anzahlaccounts_mit_dem_Schema +1)**)
     */
     
     //
     var accountname =  $firstname.charAt(0)+''+$surname;
     
     // toLowerCase
     accountname = accountname.toLowerCase();
  
     // Leerzeichen entfernen
     accountname = accountname.replace(' ', '');
     
     // deutsche Umlaute ersetzen
     accountname = accountname.replace(/ä/g, 'ae');
     accountname = accountname.replace(/ö/g, 'oe');
     accountname = accountname.replace(/ü/g, 'ue');
     accountname = accountname.replace(/ß/g, 'ss');
  
     //HSOG: sonstige Akzentumlaute 
     accountname = accountname.replace(new RegExp(/[èéêë]/g),"e");
     accountname = accountname.replace(new RegExp(/[àáâãå]/g),"a");
  	 accountname = accountname.replace(new RegExp(/[òóôõ]/g),"o");
     accountname = accountname.replace(new RegExp(/[ùúû]/g),"u");
     accountname = accountname.replace(new RegExp(/æ/g),"ae");
     accountname = accountname.replace(new RegExp(/ç/g),"c");
     accountname = accountname.replace(new RegExp(/[ìíîï]/g),"i");
     accountname = accountname.replace(new RegExp(/ñ/g),"n");                   
     accountname = accountname.replace(new RegExp(/œ/g),"oe"); 
     accountname = accountname.replace(new RegExp(/[ýÿ]/g),"y");
  	 //accountname = decodeURIComponent(escape(accountname));
     
     //HSOG: kürzen auf 8 Buchstaben
  	 accountname = accountname.substring(0, 8); 
  
     return accountname;
  
}
accNameGen();