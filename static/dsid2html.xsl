<?xml version="1.0" encoding="UTF8"?>
<!--
To reference this file from an xml file include the following
line under the <?xml ... ?> declaration.

<?xml-stylesheet type="text/xsl" href="dsid2html_example.xsl"?>

href must be specified exactly or relative to the xml files location
-->
<xsl:stylesheet version="2.0"
	xmlns:dsid="http://www.das2.org/dsid/0.2"
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:output method="html"/>

<xsl:variable name="title">
	<xsl:value-of select="dsid:dasDSID/@name"/> DSID
</xsl:variable>

<xsl:template match="/">
	<xsl:apply-templates select="dsid:dasDSID"/>
</xsl:template>

<xsl:template match="dsid:dasDSID">

<html>
<head>
	<title><xsl:value-of select="$title"/></title>
</head>
<body>
<h1><img src="http://www-pw.physics.uiowa.edu/das2/das2logo-130.png"/></h1>
<h2><xsl:value-of select="$title"/></h2>
<h3><xsl:value-of select="dsid:summary"/></h3>
<p><xsl:value-of select="dsid:description"/></p>


<hr/>
<xsl:apply-templates select="dsid:maintainer"/>

</body>
</html>

</xsl:template>

<xsl:template match="dsid:maintainer">
	<p>Maintainer: <a>
		<xsl:attribute name="href">
			mailto:<xsl:value-of select="@email"/>
		</xsl:attribute>
		<xsl:value-of select="@name"/>
	</a></p>
</xsl:template>

</xsl:stylesheet>
